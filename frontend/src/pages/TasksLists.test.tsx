import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
const post = vi.fn();
const del = vi.fn();
vi.mock("../api/client", () => ({
  api: { GET: (...a: unknown[]) => get(...a), POST: (...a: unknown[]) => post(...a), PATCH: vi.fn(), DELETE: (...a: unknown[]) => del(...a) },
  authHeader: async () => null,
  sessionRejected: vi.fn(),
}));
vi.mock("../auth", () => ({ useAuth: () => ({ user: { id: 1, display_name: "Ann" } }) }));

import { useSelectedList } from "../tasks/dayLists";
import { renderHook, act } from "@testing-library/react";
import TasksPage from "./TasksPage";

const task = (id: number, extra: Record<string, unknown>) => ({
  id, title: `Task ${id}`, description: "", status: "todo", priority: "normal", due_date: null, recurrence: null,
  assignee_id: null, feature_id: null, tray_id: null, planting_id: null, location: null, completed_at: null, completed_by: null,
  created_at: "2026-10-30T10:00:00Z", ...extra,
});
const TASKS = [task(1, { title: "Water the beans" }), task(2, { title: "Prune the apple" }), task(3, { title: "Order seed" })];
const list = (id: number, name: string, task_ids: number[]) => ({ id, name, date: null, task_ids, task_count: task_ids.length, done_count: 0, created_at: "2026-11-01T10:00:00Z" });
let lists = [list(10, "Saturday", [2]), list(11, "Watering round", [])];

function setup(role: "owner" | "viewer" = "owner") {
  const context = { id: 1, allotment: { id: 1, name: "Plot", role }, canEdit: role !== "viewer" };
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={["/a/tasks"]}>
        <Routes>
          <Route path="/a" element={<Outlet context={context} />}>
            <Route path="tasks" element={<TasksPage />} />
            <Route path="today" element={<p>today page</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  for (const m of [get, post, del]) m.mockReset();
  localStorage.clear();
  const { result } = renderHook(() => useSelectedList(1));
  act(() => result.current[1](null));
  lists = [list(10, "Saturday", [2]), list(11, "Watering round", [])];
  get.mockImplementation(async (p: string) => {
    if (p.endsWith("/day-lists")) return { data: lists };
    if (p.endsWith("/tasks")) return { data: TASKS };
    return { data: [] };
  });
  post.mockImplementation(async (p: string, opts: { body: { task_ids?: number[]; name?: string }; params: { path: { list_id?: number } } }) => {
    if (p.endsWith("/day-lists")) return { data: list(12, opts.body.name!, opts.body.task_ids ?? []) };
    return { data: lists.find((l) => l.id === opts.params.path.list_id) ?? lists[0] };
  });
});

const rowOf = (title: string) => screen.getByRole("button", { name: title }).closest("li")!;

describe("Day lists on the Tasks page", () => {
  it("shows which lists a task is on", async () => {
    setup();
    await screen.findByRole("button", { name: "Prune the apple" });
    await waitFor(() => expect(within(rowOf("Prune the apple")).getByText(/Saturday/)).toBeInTheDocument());
    expect(rowOf("Water the beans").querySelector(".on-list")).toBeNull();
  });

  it("adds a task to a chosen list, then offers a quick add to that list", async () => {
    setup();
    await screen.findByRole("button", { name: "Water the beans" });
    expect(screen.queryByRole("button", { name: /^Add .* to Watering round$/ })).not.toBeInTheDocument();
    const menu = await within(rowOf("Water the beans")).findByLabelText("Add Water the beans to a list");
    await waitFor(() => expect(within(menu).getByRole("option", { name: "Watering round" })).toBeInTheDocument());
    await userEvent.selectOptions(menu, "11");
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][1].body).toEqual({ task_ids: [1] });
    expect(post.mock.calls[0][1].params.path.list_id).toBe(11);
    expect(await screen.findByRole("status")).toHaveTextContent("Added 1 task to Watering round");
    expect(screen.getByRole("link", { name: "Open the sheet" })).toHaveAttribute("href", "/a/today?list=11");
    // Watering round is now the selected list, so every other task gets a one-click button for it.
    await userEvent.click(await screen.findByRole("button", { name: "Add Prune the apple to Watering round" }));
    await waitFor(() => expect(post).toHaveBeenCalledTimes(2));
    expect(post.mock.calls[1][1].body).toEqual({ task_ids: [2] });
  });

  it("makes a new list from the menu and puts the task on it", async () => {
    setup();
    const menu = await within(await screen.findByRole("button", { name: "Order seed" }).then((b) => b.closest("li")!)).findByLabelText("Add Order seed to a list");
    await userEvent.selectOptions(menu, "new");
    await userEvent.type(await screen.findByLabelText("New list name"), "Sunday");
    await userEvent.click(screen.getByRole("button", { name: "Add list" }));
    await waitFor(() => expect(post.mock.calls.length).toBeGreaterThanOrEqual(2));
    expect(post.mock.calls[0][1].body).toEqual({ name: "Sunday", date: null });
    expect(post.mock.calls[1][1].body).toEqual({ task_ids: [3] });
    expect(post.mock.calls[1][1].params.path.list_id).toBe(12);
  });

  it("adds all the selected tasks to a list at once", async () => {
    setup();
    await userEvent.click(await screen.findByRole("button", { name: "Select" }));
    await userEvent.click(screen.getByLabelText("Select Water the beans"));
    await userEvent.click(screen.getByLabelText("Select Order seed"));
    const bar = screen.getByRole("group", { name: "Selected tasks" });
    await waitFor(() => expect(within(bar).getByRole("option", { name: "Saturday" })).toBeInTheDocument());
    await userEvent.selectOptions(within(bar).getByLabelText("Day list for the selected tasks"), "10");
    await userEvent.click(within(bar).getByRole("button", { name: "Add to list" }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][1].body.task_ids.sort()).toEqual([1, 3]);
    expect(await screen.findByRole("status")).toHaveTextContent("Added 2 tasks to Saturday");
    expect(screen.queryByRole("group", { name: "Selected tasks" })).not.toBeInTheDocument();
  });

  it("gives viewers the chips but no way to add", async () => {
    setup("viewer");
    await screen.findByRole("button", { name: "Prune the apple" });
    await waitFor(() => expect(within(rowOf("Prune the apple")).getByText(/Saturday/)).toBeInTheDocument());
    expect(screen.queryByLabelText(/to a list/)).not.toBeInTheDocument();
  });
});

describe("Day lists in the task dialog", () => {
  it("shows the lists a task is on and takes it off one", async () => {
    del.mockResolvedValue({});
    setup();
    await userEvent.click(await screen.findByRole("button", { name: "Prune the apple" }));
    const dialog = await screen.findByRole("dialog", { name: /task/i }).catch(() => document.querySelector("dialog")!);
    await userEvent.click(await within(dialog as HTMLElement).findByRole("button", { name: "Take this task off Saturday" }));
    await waitFor(() => expect(del).toHaveBeenCalled());
    expect(del.mock.calls[0][1].params.path).toEqual({ allotment_id: 1, list_id: 10, task_id: 2 });
  });
});
