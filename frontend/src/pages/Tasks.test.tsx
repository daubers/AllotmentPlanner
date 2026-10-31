import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
const post = vi.fn();
const patch = vi.fn();
vi.mock("../api/client", () => ({
  api: { GET: (...a: unknown[]) => get(...a), POST: (...a: unknown[]) => post(...a), PATCH: (...a: unknown[]) => patch(...a), DELETE: vi.fn() },
  authHeader: async () => null,
  sessionRejected: vi.fn(),
}));
vi.mock("../auth", () => ({ useAuth: () => ({ user: { id: 1, display_name: "Ann" } }) }));

import TasksPage from "./TasksPage";

const task = (id: number, extra: Record<string, unknown>) => ({
  id, title: `Task ${id}`, description: "", status: "todo", priority: "normal", due_date: null, recurrence: null,
  assignee_id: null, feature_id: null, tray_id: null, planting_id: null, location: null, completed_at: null, completed_by: null,
  created_at: "2026-10-30T10:00:00Z", ...extra,
});
const TASKS = [
  task(1, { title: "Water the beans", priority: "high", assignee_id: 1, feature_id: 5, due_date: "2099-01-01" }),
  task(2, { title: "Prune the apple", assignee_id: 2, due_date: "2099-01-02" }),
  task(3, { title: "Order seed", description: "from the beans supplier" }),
];

function setup(url = "/a/tasks", role: "owner" | "viewer" = "owner") {
  const context = { id: 1, allotment: { id: 1, name: "Plot", role }, canEdit: role !== "viewer" };
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/a" element={<Outlet context={context} />}>
            <Route path="tasks" element={<TasksPage />} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  for (const m of [get, post, patch]) m.mockReset();
  get.mockImplementation(async (p: string) => {
    if (p.endsWith("/tasks")) return { data: TASKS };
    if (p.endsWith("/features")) return { data: { features: [{ id: 5, geometry: {}, properties: { name: "Bed 1", kind: "bed" } }] } };
    if (p.endsWith("/members")) return { data: [{ user_id: 1, display_name: "Ann" }, { user_id: 2, display_name: "Bob" }] };
    return { data: [] };
  });
  post.mockResolvedValue({ data: { tasks: [], deleted: [] } });
  patch.mockResolvedValue({ data: { id: 1 } });
});

const titles = () => screen.getAllByRole("button", { name: /^(Water|Prune|Order)/ }).map((b) => b.textContent);

describe("Tasks page", () => {
  it("lists every task and who it is for", async () => {
    setup();
    expect(await screen.findByRole("button", { name: "Water the beans" })).toBeInTheDocument();
    expect(titles()).toHaveLength(3);
    expect(screen.getByText("👤 Bob")).toBeInTheDocument();
  });

  it("searches titles and notes", async () => {
    setup();
    await screen.findByRole("button", { name: "Water the beans" });
    await userEvent.type(screen.getByLabelText("Search tasks"), "beans");
    expect(titles()).toEqual(["Water the beans", "Order seed"]);
    await userEvent.type(screen.getByLabelText("Search tasks"), " zzz");
    expect(await screen.findByText("No tasks match those filters.")).toBeInTheDocument();
  });

  it("shows only my tasks from the URL, and clears the filters", async () => {
    setup("/a/tasks?who=me");
    await screen.findByRole("button", { name: "Water the beans" });
    expect(titles()).toEqual(["Water the beans"]);
    await userEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(titles()).toHaveLength(3);
  });

  it("sorts by priority", async () => {
    setup();
    await screen.findByRole("button", { name: "Water the beans" });
    await userEvent.selectOptions(screen.getByLabelText("Sort by"), "priority");
    expect(titles()[0]).toBe("Water the beans");
    await userEvent.selectOptions(screen.getByLabelText("Sort by"), "newest");
    expect(titles()[0]).toBe("Order seed");
  });

  it("reschedules a task from its menu", async () => {
    setup();
    await screen.findByRole("button", { name: "Prune the apple" });
    await userEvent.selectOptions(screen.getByLabelText("Reschedule Prune the apple"), "No date");
    await waitFor(() => expect(patch).toHaveBeenCalled());
    expect(patch.mock.calls[0][1]).toMatchObject({ params: { path: { task_id: 2 } }, body: { due_date: null } });
  });

  it("completes several at once", async () => {
    setup();
    await screen.findByRole("button", { name: "Water the beans" });
    await userEvent.click(screen.getByRole("button", { name: "Select" }));
    await userEvent.click(screen.getByLabelText("Select Water the beans"));
    await userEvent.click(screen.getByLabelText("Select Order seed"));
    const bar = screen.getByRole("group", { name: "Selected tasks" });
    expect(within(bar).getByText("2 selected")).toBeInTheDocument();
    await userEvent.click(within(bar).getByRole("button", { name: "Complete" }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][1].body).toEqual({ ids: [1, 3], action: "complete" });
    await waitFor(() => expect(screen.queryByRole("group", { name: "Selected tasks" })).not.toBeInTheDocument());
  });

  it("asks before deleting a selection", async () => {
    setup();
    await screen.findByRole("button", { name: "Water the beans" });
    await userEvent.click(screen.getByRole("button", { name: "Select" }));
    await userEvent.click(screen.getByLabelText("Select Prune the apple"));
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(post).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Yes, delete" }));
    await waitFor(() => expect(post.mock.calls[0][1].body).toEqual({ ids: [2], action: "delete" }));
  });

  it("gives a viewer the list and filters but no editing controls", async () => {
    setup("/a/tasks", "viewer");
    await screen.findByRole("button", { name: "Water the beans" });
    expect(screen.queryByRole("button", { name: "+ New task" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Select" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Reschedule Prune the apple")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Search tasks")).toBeInTheDocument();
  });
});
