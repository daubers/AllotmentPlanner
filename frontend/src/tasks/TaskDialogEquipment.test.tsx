import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
const post = vi.fn();
const patch = vi.fn();
vi.mock("../api/client", () => ({
  api: { GET: (...a: unknown[]) => get(...a), POST: (...a: unknown[]) => post(...a), PATCH: (...a: unknown[]) => patch(...a), DELETE: vi.fn() },
  authHeader: async () => null,
  sessionRejected: vi.fn(),
}));

import TaskDialog from "./TaskDialog";
import type { Task } from "./group";

const eq = (id: number, name: string, kind = "spade") => ({ id, name, kind, kind_label: "Spade", quantity: 1, notes: "", used_for: "", keywords: [], status: "in_service" });
const SPADE = eq(1, "Border spade");
const FORK = eq(2, "Hand fork", "hand_fork");
const DIBBER = eq(3, "Dibber", "dibber");
const suggest = vi.fn();

function setup(props: Partial<React.ComponentProps<typeof TaskDialog>> = {}) {
  const onClose = vi.fn();
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <TaskDialog allotmentId={1} canEdit onClose={onClose} {...props} />
    </QueryClientProvider>,
  );
  return onClose;
}

beforeEach(() => {
  for (const m of [get, post, patch, suggest]) m.mockReset();
  get.mockImplementation(async (p: string) => {
    if (p.endsWith("/equipment")) return { data: [SPADE, FORK, DIBBER] };
    if (p.endsWith("/members")) return { data: [] };
    if (p.endsWith("/features")) return { data: { features: [] } };
    return { data: [] };
  });
  suggest.mockResolvedValue([]);
  post.mockImplementation(async (p: string, init: unknown) => {
    if (p.endsWith("/equipment/suggest")) return { data: await suggest(init) };
    return { data: { id: 10 } };
  });
  patch.mockResolvedValue({ data: { id: 9 } });
});

const task: Task = {
  id: 9, title: "Dig the bed", description: "", status: "todo", priority: "normal", due_date: null, recurrence: null, assignee_id: null,
  feature_id: null, tray_id: null, planting_id: null, location: null, completed_at: null, completed_by: null, created_at: "2026-10-30T10:00:00Z",
  equipment: [{ id: 1, name: "Border spade", kind: "spade", kind_label: "Spade", quantity: 1, status: "in_service" }],
};

describe("Equipment in the task dialog", () => {
  it("suggests equipment once you have typed a title, and a click adds it", async () => {
    suggest.mockResolvedValue([{ ...SPADE, reason: "digging" }]);
    setup();
    await userEvent.type(screen.getByLabelText("Title"), "Dig the bed");
    const chip = await screen.findByRole("button", { name: "Add Border spade" }, { timeout: 3000 });
    expect(chip).toHaveAttribute("title", "Suggested for digging");
    expect(suggest).toHaveBeenCalledTimes(1); // one request for the finished title, not one per key
    expect(post.mock.calls.find((c) => String(c[0]).endsWith("/equipment/suggest"))![1].body).toMatchObject({ title: "Dig the bed", exclude_ids: [] });
    await userEvent.click(chip);
    expect(await screen.findByRole("button", { name: "Remove Border spade" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add Border spade" })).not.toBeInTheDocument();
  });

  it("does not suggest for a very short title", async () => {
    setup();
    await userEvent.type(screen.getByLabelText("Title"), "Di");
    await new Promise((r) => setTimeout(r, 600));
    expect(suggest).not.toHaveBeenCalled();
  });

  it("saves the equipment with a new task", async () => {
    suggest.mockResolvedValue([{ ...SPADE, reason: "digging" }]);
    const onClose = setup();
    await userEvent.type(screen.getByLabelText("Title"), "Dig the bed");
    await userEvent.click(await screen.findByRole("button", { name: "Add Border spade" }, { timeout: 3000 }));
    await userEvent.selectOptions(screen.getByLabelText("Add equipment"), "Dibber");
    await userEvent.click(screen.getByRole("button", { name: "Add task" }));
    await waitFor(() => expect(post.mock.calls.some((c) => String(c[0]).endsWith("/tasks"))).toBe(true));
    const create = post.mock.calls.find((c) => String(c[0]).endsWith("/tasks"))!;
    expect(create[1].body).toMatchObject({ title: "Dig the bed", equipment_ids: [1, 3] });
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it("shows the equipment a task has and saves a change to it", async () => {
    setup({ task });
    expect(await screen.findByText(/Border spade/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Remove Border spade" }));
    await userEvent.selectOptions(screen.getByLabelText("Add equipment"), "Hand fork");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(patch).toHaveBeenCalled());
    expect(patch.mock.calls[0][1].body.equipment_ids).toEqual([2]);
  });

  it("leaves the equipment as it was when only the title changes", async () => {
    setup({ task });
    await screen.findByText(/Border spade/);
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(patch).toHaveBeenCalled());
    expect(patch.mock.calls[0][1].body.equipment_ids).toEqual([1]);
  });

  it("does not suggest what is already on the task", async () => {
    setup({ task });
    await screen.findByText(/Border spade/);
    await userEvent.type(screen.getByLabelText("Notes"), "needs digging over");
    await waitFor(() => expect(suggest).toHaveBeenCalled(), { timeout: 3000 });
    expect(suggest.mock.calls.at(-1)![0].body.exclude_ids).toEqual([1]);
  });

  it("only shows a viewer what is on the task", async () => {
    setup({ task, canEdit: false });
    expect(await screen.findByText(/Border spade/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Remove Border spade" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Add equipment")).not.toBeInTheDocument();
    expect(suggest).not.toHaveBeenCalled();
  });

  it("does not take equipment for a repeating schedule", async () => {
    setup();
    expect(screen.getByText("Equipment")).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Repeats"), "On a schedule…");
    expect(screen.queryByText("Equipment")).not.toBeInTheDocument();
  });
});
