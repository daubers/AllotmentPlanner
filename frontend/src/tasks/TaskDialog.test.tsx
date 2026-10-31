import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
const post = vi.fn();
const patch = vi.fn();
const del = vi.fn();
vi.mock("../api/client", () => ({
  api: {
    GET: (...a: unknown[]) => get(...a),
    POST: (...a: unknown[]) => post(...a),
    PATCH: (...a: unknown[]) => patch(...a),
    DELETE: (...a: unknown[]) => del(...a),
  },
  authHeader: async () => null,
  sessionRejected: vi.fn(),
}));

import TaskDialog, { placeFromValue, placeValue } from "./TaskDialog";
import type { Task } from "./group";

const task: Task = {
  id: 9, title: "Water the beans", description: "Both rows", status: "todo", priority: "high", due_date: "2026-11-02",
  recurrence: "weekly", assignee_id: 2, feature_id: 5, tray_id: null, planting_id: null, location: null,
  completed_at: null, completed_by: null, created_at: "2026-10-30T10:00:00Z",
};

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
  for (const m of [get, post, patch, del]) m.mockReset();
  get.mockImplementation(async (p: string) => {
    if (p.endsWith("/features")) return { data: { features: [{ id: 5, geometry: {}, properties: { name: "Bed 1", kind: "bed" } }] } };
    if (p.endsWith("/members")) return { data: [{ user_id: 1, display_name: "Ann" }, { user_id: 2, display_name: "Bob" }] };
    return { data: [] };
  });
  post.mockResolvedValue({ data: { id: 10 } });
  patch.mockResolvedValue({ data: { id: 9 } });
  del.mockResolvedValue({});
});

describe("place helpers", () => {
  it("round-trips a feature, tray or planting", () => {
    expect(placeValue({ tray_id: 3 })).toBe("tray:3");
    expect(placeFromValue("planting:4")).toEqual({ feature_id: null, tray_id: null, planting_id: 4 });
    expect(placeFromValue("")).toEqual({ feature_id: null, tray_id: null, planting_id: null });
  });
});

describe("TaskDialog", () => {
  it("creates a task with notes, assignee and place, then closes", async () => {
    const onClose = setup({ place: { feature_id: 5 } });
    await screen.findByRole("option", { name: "Bob" });
    await userEvent.type(screen.getByLabelText("Title"), "Weed");
    await userEvent.type(screen.getByLabelText("Notes"), "Edges too");
    await userEvent.selectOptions(screen.getByLabelText("Assigned to"), "Bob");
    await userEvent.click(screen.getByRole("button", { name: "Add task" }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    const body = post.mock.calls[0][1].body;
    expect(body).toMatchObject({ title: "Weed", description: "Edges too", assignee_id: 2, feature_id: 5, tray_id: null, status: "todo" });
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it("edits an existing task with a PATCH", async () => {
    const onClose = setup({ task });
    await screen.findByRole("option", { name: "Bob" });
    expect(screen.getByLabelText("Title")).toHaveValue("Water the beans");
    expect(screen.getByLabelText("Where")).toHaveValue("feature:5");
    await userEvent.clear(screen.getByLabelText("Title"));
    await userEvent.type(screen.getByLabelText("Title"), "Water the peas");
    await userEvent.selectOptions(screen.getByLabelText("Status"), "doing");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(patch).toHaveBeenCalled());
    expect(patch.mock.calls[0][1].params.path.task_id).toBe(9);
    expect(patch.mock.calls[0][1].body).toMatchObject({ title: "Water the peas", status: "doing", priority: "high", recurrence: "weekly" });
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it("shows the server's message and stays open when saving fails", async () => {
    patch.mockResolvedValue({ error: { message: "assignee_id is not a member of this allotment" } });
    const onClose = setup({ task });
    await screen.findByRole("option", { name: "Bob" });
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("not a member");
    expect(onClose).not.toHaveBeenCalled();
  });

  it("asks before deleting", async () => {
    const onClose = setup({ task });
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(del).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Yes, delete" }));
    await waitFor(() => expect(del).toHaveBeenCalled());
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it("names who completed a done task and does not offer to change its status", async () => {
    setup({ task: { ...task, status: "done", completed_by: 1, completed_at: "2026-11-01T09:00:00Z" } });
    expect(await screen.findByText(/Done by Ann on 01\/11\/2026/)).toBeInTheDocument();
    expect(screen.getByLabelText("Status")).toBeDisabled();
  });

  it("is read-only for a viewer", () => {
    setup({ task, canEdit: false });
    expect(screen.getByLabelText("Title")).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument();
  });
});
