import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
const post = vi.fn();
const patch = vi.fn();
vi.mock("../api/client", () => ({
  api: { GET: (...a: unknown[]) => get(...a), POST: (...a: unknown[]) => post(...a), PATCH: (...a: unknown[]) => patch(...a), DELETE: vi.fn() },
  authHeader: async () => null,
  sessionRejected: vi.fn(),
  getSession: () => null,
}));

import VisitDialog from "./VisitDialog";
import type { Visit } from "./hooks";

const eq = (id: number, name: string) => ({ id, name, kind: null, kind_label: "Other", quantity: 1, notes: "", used_for: "", keywords: [], status: "in_service" });
const brief = (id: number, name: string) => ({ id, name, kind: null, kind_label: "Other", quantity: 1, status: "in_service" });
const task = (id: number, title: string, equipment: ReturnType<typeof brief>[] = []) => ({
  id, title, description: "", status: "todo", priority: "normal", due_date: null, recurrence: null, assignee_id: null, feature_id: null,
  tray_id: null, planting_id: null, location: null, completed_at: null, completed_by: null, created_at: "2026-10-30T10:00:00Z", equipment,
});
const DIG = task(1, "Dig the bed", [brief(1, "Border spade"), brief(2, "Fork")]);
const SOW = task(2, "Sow carrots", [brief(3, "Dibber")]);
const BARE = task(3, "Think about beans");

function setup(visit: Visit | "new" = "new") {
  const onClose = vi.fn();
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <VisitDialog allotmentId={1} visit={visit} onClose={onClose} />
    </QueryClientProvider>,
  );
  return onClose;
}

const bringBox = () => within(screen.getByRole("group", { name: "Equipment" }));
// A tool on the list is a chip with a Remove button; the same names also sit in the "Add equipment" menu.
const listed = (name: string) => screen.queryByRole("button", { name: `Remove ${name}` });

beforeEach(() => {
  for (const m of [get, post, patch]) m.mockReset();
  get.mockImplementation(async (p: string) => {
    if (p.endsWith("/tasks")) return { data: [DIG, SOW, BARE] };
    if (p.endsWith("/equipment")) return { data: [eq(1, "Border spade"), eq(2, "Fork"), eq(3, "Dibber"), eq(5, "Wheelbarrow")] };
    return { data: [] };
  });
  post.mockResolvedValue({ data: { id: 9 } });
  patch.mockResolvedValue({ data: { id: 9 } });
});

const visit = (extra: Partial<Visit> = {}): Visit => ({
  id: 9, title: "Saturday", notes: "", starts_at: "2026-11-07T09:00:00Z", duration_minutes: 90, task_ids: [1], bring: [], equipment_extras: [], ...extra,
}) as Visit;

describe("Equipment to bring", () => {
  it("shows what the picked jobs need, and follows the picking", async () => {
    setup();
    await userEvent.click(await screen.findByRole("checkbox", { name: "Dig the bed" }));
    expect(await screen.findByRole("button", { name: "Remove Border spade" })).toBeInTheDocument();
    expect(listed("Fork")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("checkbox", { name: "Sow carrots" }));
    expect(listed("Dibber")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("checkbox", { name: "Dig the bed" }));
    expect(listed("Border spade")).not.toBeInTheDocument();
    expect(listed("Dibber")).toBeInTheDocument();
  });

  it("says nothing is needed when no job needs anything", async () => {
    setup();
    await userEvent.click(await screen.findByRole("checkbox", { name: "Think about beans" }));
    expect(await bringBox().findByText("None needed")).toBeInTheDocument();
  });

  it("sends the hand-made changes when the visit is planned", async () => {
    const onClose = setup();
    await userEvent.type(await screen.findByLabelText("Title"), "Saturday");
    await userEvent.click(screen.getByRole("checkbox", { name: "Dig the bed" }));
    await userEvent.click(await bringBox().findByRole("button", { name: "Remove Fork" })); // a job needs it, but leave it at home
    await userEvent.selectOptions(bringBox().getByLabelText("Add equipment"), "Wheelbarrow"); // and take this
    await userEvent.click(screen.getByRole("button", { name: "Plan visit" }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][1].body).toMatchObject({ title: "Saturday", task_ids: [1], equipment_adds: [5], equipment_removes: [2] });
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it("takes a hand-added tool back off without hiding anything", async () => {
    setup();
    await userEvent.type(await screen.findByLabelText("Title"), "Saturday");
    await userEvent.selectOptions(await bringBox().findByLabelText("Add equipment"), "Wheelbarrow");
    await userEvent.click(bringBox().getByRole("button", { name: "Remove Wheelbarrow" }));
    await userEvent.click(screen.getByRole("button", { name: "Plan visit" }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][1].body).toMatchObject({ equipment_adds: [], equipment_removes: [] });
  });

  it("starts from the changes already saved and sends the new ones", async () => {
    const saved = visit({ equipment_extras: [{ equipment_id: 5, mode: "add" }, { equipment_id: 2, mode: "remove" }] });
    setup(saved);
    expect(await screen.findByRole("button", { name: "Remove Wheelbarrow" })).toBeInTheDocument();
    expect(listed("Fork")).not.toBeInTheDocument(); // hidden
    expect(listed("Border spade")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(patch).toHaveBeenCalled());
    expect(patch.mock.calls[0][1].body).toMatchObject({ equipment_adds: [5], equipment_removes: [2] });
  });

  it("brings back a hidden tool when it is added again", async () => {
    setup(visit({ equipment_extras: [{ equipment_id: 2, mode: "remove" }] }));
    await screen.findByRole("button", { name: "Remove Border spade" });
    expect(listed("Fork")).not.toBeInTheDocument();
    await userEvent.selectOptions(bringBox().getByLabelText("Add equipment"), "Fork");
    expect(listed("Fork")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(patch).toHaveBeenCalled());
    expect(patch.mock.calls[0][1].body).toMatchObject({ equipment_adds: [], equipment_removes: [] }); // a task needs it anyway
  });

  it("keeps the suggestions the server made for jobs with no tools", async () => {
    const saved = visit({ task_ids: [3], bring: [{ ...brief(3, "Dibber"), source: "suggested", task_ids: [3] }] as Visit["bring"] });
    setup(saved);
    expect(await screen.findByRole("button", { name: "Remove Dibber" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("checkbox", { name: "Think about beans" })); // unpick that job
    expect(listed("Dibber")).not.toBeInTheDocument();
  });
});
