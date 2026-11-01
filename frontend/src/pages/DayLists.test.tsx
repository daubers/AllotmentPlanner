import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
const post = vi.fn();
const patch = vi.fn();
const del = vi.fn();
vi.mock("../api/client", () => ({
  api: { GET: (...a: unknown[]) => get(...a), POST: (...a: unknown[]) => post(...a), PATCH: (...a: unknown[]) => patch(...a), DELETE: (...a: unknown[]) => del(...a) },
  authHeader: async () => null,
  sessionRejected: vi.fn(),
}));

import TodayPage from "./TodayPage";

const task = (id: number, extra: Record<string, unknown>) => ({
  id, title: `Task ${id}`, description: "", status: "todo", priority: "normal", due_date: "2026-11-02", recurrence: null,
  assignee_id: null, feature_id: null, tray_id: null, planting_id: null, location: null, ...extra,
});
const ALL = [task(1, { title: "Water the beans" }), task(2, { title: "Weed the paths" }), task(3, { title: "Order seed", due_date: null })];
const LIST = { id: 3, name: "Saturday", date: "2026-11-07", task_ids: [1, 4], task_count: 2, done_count: 1, created_at: "2026-11-01T10:00:00Z" };
const SHEET = {
  date: "2026-11-07", title: "Saturday", allotment: { id: 1, name: "Plot" }, features: [], members: [],
  tasks: [task(1, { title: "Water the beans" }), task(4, { title: "Mend the shed", status: "done" })],
};

function setup(url = "/a/today?list=3", role: "owner" | "viewer" = "owner") {
  const context = { id: 1, allotment: { id: 1, name: "Plot", role }, canEdit: role !== "viewer" };
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/a" element={<Outlet context={context} />}>
            <Route path="today" element={<TodayPage />} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  for (const m of [get, post, patch, del]) m.mockReset();
  get.mockImplementation(async (p: string) => {
    if (p.endsWith("/day-lists")) return { data: [LIST] };
    if (p.endsWith("/day-lists/{list_id}/todo")) return { data: SHEET };
    if (p.endsWith("/todo")) return { data: { date: "2026-11-02", allotment: { id: 1, name: "Plot" }, tasks: [task(9, { title: "Due today" })], features: [], members: [] } };
    if (p.endsWith("/tasks")) return { data: ALL };
    return { data: [] };
  });
  post.mockResolvedValue({ data: LIST });
  del.mockResolvedValue({});
});

describe("Today with a day list", () => {
  it("shows the list's jobs under its name, with finished ones already ticked", async () => {
    setup();
    expect(await screen.findByRole("heading", { name: "Saturday" })).toBeInTheDocument();
    expect(screen.getByLabelText("Complete Water the beans")).not.toBeChecked();
    expect(screen.getByLabelText("Reopen Mend the shed")).toBeChecked();
    expect(screen.queryByText("Due today")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Date")).not.toBeInTheDocument();
  });

  it("is the usual due-today sheet until a list is chosen, and switching adds ?list to the page", async () => {
    setup("/a/today?date=2026-11-02");
    expect(await screen.findByText("Due today")).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("List"), "3");
    expect(await screen.findByRole("heading", { name: "Saturday" })).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("List"), "");
    expect(await screen.findByText("Due today")).toBeInTheDocument();
  });

  it("takes a job off the list without deleting it", async () => {
    setup();
    await userEvent.click(await screen.findByRole("button", { name: "Take Water the beans off the list" }));
    await waitFor(() => expect(del).toHaveBeenCalled());
    expect(del.mock.calls[0][0]).toContain("/day-lists/{list_id}/tasks/{task_id}");
    expect(del.mock.calls[0][1].params.path).toEqual({ allotment_id: 1, list_id: 3, task_id: 1 });
  });

  it("adds open jobs that are not on the list yet", async () => {
    setup();
    await userEvent.click(await screen.findByText("Add jobs to Saturday"));
    const plan = screen.getByText("Add jobs to Saturday").closest("details")!;
    expect(await within(plan).findByLabelText(/Weed the paths/)).toBeInTheDocument();
    expect(within(plan).queryByLabelText(/Water the beans/)).not.toBeInTheDocument(); // already on it
    await userEvent.type(within(plan).getByLabelText("Search the jobs"), "seed");
    expect(within(plan).queryByLabelText(/Weed the paths/)).not.toBeInTheDocument();
    await userEvent.click(within(plan).getByLabelText(/Order seed/));
    await userEvent.click(within(plan).getByRole("button", { name: /Add 1 to list/ }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][1].body).toEqual({ task_ids: [3] });
    expect(post.mock.calls[0][1].params.path.list_id).toBe(3);
  });

  it("lets viewers see a list but not change it", async () => {
    setup("/a/today?list=3", "viewer");
    await screen.findByRole("heading", { name: "Saturday" });
    expect(screen.queryByText("Add jobs to Saturday")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /off the list/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Lists" })).toBeInTheDocument();
  });
});

describe("Manage lists", () => {
  it("makes a list and switches to it", async () => {
    post.mockResolvedValue({ data: { ...LIST, id: 8, name: "Evening", task_ids: [] } });
    setup("/a/today?date=2026-11-02");
    await userEvent.click(await screen.findByRole("button", { name: "Manage lists" }));
    await userEvent.type(screen.getByLabelText("New list name"), "Evening");
    await userEvent.click(screen.getByRole("button", { name: "Add list" }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][1].body).toEqual({ name: "Evening", date: null });
  });

  it("renames a list and clears its date", async () => {
    patch.mockResolvedValue({ data: LIST });
    setup("/a/today?date=2026-11-02");
    await userEvent.click(await screen.findByRole("button", { name: "Manage lists" }));
    const name = await screen.findByLabelText("Name of Saturday");
    await userEvent.clear(name);
    await userEvent.type(name, "Saturday am");
    await userEvent.clear(screen.getByLabelText("Date of Saturday"));
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(patch).toHaveBeenCalled());
    expect(patch.mock.calls[0][1].body).toEqual({ name: "Saturday am", date: null });
  });

  it("asks before deleting a list", async () => {
    setup("/a/today?date=2026-11-02");
    await userEvent.click(await screen.findByRole("button", { name: "Manage lists" }));
    await userEvent.click(await screen.findByRole("button", { name: "Delete" }));
    expect(del).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: /Really delete Saturday/ }));
    await waitFor(() => expect(del).toHaveBeenCalled());
    expect(del.mock.calls[0][1].params.path.list_id).toBe(3);
  });
});
