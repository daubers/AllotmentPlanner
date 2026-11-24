import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
const post = vi.fn();
vi.mock("../api/client", () => ({
  api: { GET: (...a: unknown[]) => get(...a), POST: (...a: unknown[]) => post(...a), PATCH: vi.fn(), DELETE: vi.fn() },
  authHeader: async () => null,
  sessionRejected: vi.fn(),
}));

import BookEquipmentDialog from "./BookEquipmentDialog";

const eq = (id: number, name: string, quantity = 1, status = "in_service") => ({ id, name, kind: "cloche", kind_label: "Cloche", quantity, notes: "", used_for: "", keywords: [], status });
let existing: unknown[] = [];

function setup(props: Partial<React.ComponentProps<typeof BookEquipmentDialog>> = {}) {
  const onClose = vi.fn();
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <BookEquipmentDialog allotmentId={1} onClose={onClose} {...props} />
    </QueryClientProvider>,
  );
  return onClose;
}

beforeEach(() => {
  for (const m of [get, post]) m.mockReset();
  existing = [];
  get.mockImplementation(async (p: string) => {
    if (p.endsWith("/equipment-bookings")) return { data: existing };
    if (p.endsWith("/equipment")) return { data: [eq(1, "Glass cloches", 6), eq(2, "Fleece"), eq(3, "Old frame", 1, "out_of_action")] };
    if (p.endsWith("/features")) return { data: { features: [{ id: 5, geometry: {}, properties: { name: "Bed 1", kind: "bed" } }, { id: 9, geometry: {}, properties: { name: "Shed", kind: "shed" } }] } };
    return { data: [] };
  });
  post.mockResolvedValue({ data: { id: 10 } });
});

const booking = (id: number, quantity: number, starts_on: string, ends_on: string) => ({ id, equipment_id: 1, equipment_name: "Glass cloches", equipment_quantity: 6, quantity, starts_on, ends_on, note: "", warnings: [] });

describe("Put equipment to use", () => {
  it("books equipment onto the bed it was opened from", async () => {
    const onClose = setup({ target: { kind: "feature", id: 5, label: "Bed 1" } });
    await screen.findByRole("option", { name: "Glass cloches (you have 6)" }); // once the list has loaded
    await userEvent.selectOptions(screen.getByLabelText("Equipment"), "Glass cloches (you have 6)");
    expect(screen.queryByLabelText("Bed")).not.toBeInTheDocument(); // already known
    const many = screen.getByLabelText("How many");
    await userEvent.clear(many);
    await userEvent.type(many, "4");
    await userEvent.type(screen.getByLabelText("Note"), "over the lettuce");
    await userEvent.click(screen.getByRole("button", { name: "Put to use" }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][0]).toMatch(/\/equipment\/\{equipment_id\}\/bookings$/);
    expect(post.mock.calls[0][1].params.path).toEqual({ allotment_id: 1, equipment_id: 1 });
    expect(post.mock.calls[0][1].body).toMatchObject({ feature_id: 5, planting_id: null, quantity: 4, note: "over the lettuce" });
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it("books a planting", async () => {
    setup({ equipmentId: 1, target: { kind: "planting", id: 8, label: "Lettuce" } });
    await userEvent.click(await screen.findByRole("button", { name: "Put to use" }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][1].body).toMatchObject({ feature_id: null, planting_id: 8 });
  });

  it("from an item's page the item is fixed and you pick a bed, beds only", async () => {
    setup({ equipmentId: 1 });
    expect(screen.queryByLabelText("Equipment")).not.toBeInTheDocument();
    await screen.findByRole("option", { name: "Bed 1" });
    expect(screen.queryByRole("option", { name: "Shed" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Put to use" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Choose a bed.");
    expect(post).not.toHaveBeenCalled();
    await userEvent.selectOptions(screen.getByLabelText("Bed"), "Bed 1");
    await userEvent.click(screen.getByRole("button", { name: "Put to use" }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][1].body.feature_id).toBe(5);
  });

  it("offers only equipment that is in service, and asks you to choose", async () => {
    setup({ target: { kind: "feature", id: 5, label: "Bed 1" } });
    await screen.findByRole("option", { name: "Fleece" });
    expect(screen.queryByRole("option", { name: "Old frame" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Put to use" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Choose the equipment.");
  });

  it("warns, before saving, when it would be more than you own", async () => {
    const today = new Date();
    const iso = (days: number) => new Date(today.getTime() + days * 86_400_000).toISOString().slice(0, 10);
    existing = [booking(1, 5, iso(0), iso(60))];
    setup({ equipmentId: 1, target: { kind: "feature", id: 5, label: "Bed 1" } });
    const many = await screen.findByLabelText("How many");
    await userEvent.clear(many);
    await userEvent.type(many, "3");
    expect(await screen.findByRole("status")).toHaveTextContent(/You only have 6 Glass cloches: 8 would be in use from/);
    expect(screen.getByRole("status")).toHaveTextContent("You can still save it.");
    await userEvent.clear(many);
    await userEvent.type(many, "1");
    await waitFor(() => expect(screen.queryByRole("status")).not.toBeInTheDocument()); // 6 of 6 is fine
    await userEvent.click(screen.getByRole("button", { name: "Put to use" }));
    await waitFor(() => expect(post).toHaveBeenCalled()); // and a warning never blocks saving
  });

  it("does not warn for back to back use", async () => {
    const iso = (days: number) => new Date(Date.now() + days * 86_400_000).toISOString().slice(0, 10);
    existing = [booking(1, 6, iso(-30), iso(0))]; // ends the day the new one starts
    setup({ equipmentId: 1, target: { kind: "feature", id: 5, label: "Bed 1" } });
    const many = await screen.findByLabelText("How many");
    await userEvent.clear(many);
    await userEvent.type(many, "6");
    await screen.findByRole("button", { name: "Put to use" });
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("shows the server's refusal", async () => {
    post.mockResolvedValue({ error: { message: "planting_id does not belong to this allotment" } });
    setup({ equipmentId: 1, target: { kind: "planting", id: 8, label: "Lettuce" } });
    await userEvent.click(await screen.findByRole("button", { name: "Put to use" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("does not belong to this allotment");
  });
});
