import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
const post = vi.fn();
vi.mock("../api/client", () => ({
  api: { GET: (...a: unknown[]) => get(...a), POST: (...a: unknown[]) => post(...a), PATCH: vi.fn(), DELETE: vi.fn() },
  authHeader: async () => null,
  sessionRejected: vi.fn(),
}));

import TodayPage from "./TodayPage";

const task = (id: number, extra: Record<string, unknown>) => ({
  id, title: `Task ${id}`, description: "", status: "todo", priority: "normal", due_date: "2026-11-02", recurrence: null,
  assignee_id: null, feature_id: null, tray_id: null, planting_id: null, location: null, ...extra,
});
const bed = { id: 5, geometry: { type: "Polygon", coordinates: [[[-1, 51], [-1, 51.001], [-0.999, 51.001], [-1, 51]]] }, properties: { name: "Bed 1", kind: "bed" } };
let open = [task(1, { title: "Water the beans", feature_id: 5 }), task(2, { title: "Check germination", tray_id: 7 })];

function setup(role: "owner" | "viewer" = "owner") {
  const context = { id: 1, allotment: { id: 1, name: "Plot", role }, canEdit: role !== "viewer" };
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={["/a/today?date=2026-11-02"]}>
        <Routes>
          <Route path="/a" element={<Outlet context={context} />}>
            <Route path="today" element={<TodayPage />} />
            <Route path="trays/:id" element={<p>tray page</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  for (const m of [get, post]) m.mockReset();
  open = [task(1, { title: "Water the beans", feature_id: 5 }), task(2, { title: "Check germination", tray_id: 7 })];
  get.mockImplementation(async (p: string) => {
    if (p.endsWith("/todo")) return { data: { date: "2026-11-02", allotment: { id: 1, name: "Plot" }, tasks: open, features: [bed], members: [] } };
    if (p.endsWith("/trays")) return { data: [{ id: 7, name: "Spring tray" }] };
    return { data: [] };
  });
  post.mockImplementation(async (path: string) => {
    // the server stops returning a finished job, and returns it again once reopened
    open = path.endsWith("/complete") ? open.filter((t) => t.id !== 1) : [task(1, { title: "Water the beans", feature_id: 5 }), ...open];
    return { data: {} };
  });
});

describe("Today page", () => {
  it("names the tray a job is for and links to it, and links beds to their page", async () => {
    setup();
    expect(await screen.findByRole("link", { name: "Tray: Spring tray" })).toHaveAttribute("href", "/a/trays/7");
    expect(screen.getByRole("link", { name: "Bed 1" })).toHaveAttribute("href", "/a/beds/5");
  });

  it("ticks a job off on screen and keeps it, struck through, where it was", async () => {
    setup();
    await userEvent.click(await screen.findByLabelText("Complete Water the beans"));
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][0]).toContain("/complete");
    expect(post.mock.calls[0][1].params.path.task_id).toBe(1);
    const box = await screen.findByLabelText("Reopen Water the beans");
    expect(box).toBeChecked();
    expect(box.closest("li")).toHaveClass("ticked");
    await waitFor(() => expect(get.mock.calls.filter((c) => String(c[0]).endsWith("/todo")).length).toBeGreaterThan(1));
    expect(screen.getByLabelText("Reopen Water the beans")).toBeInTheDocument(); // still there after the refresh
  });

  it("reopens a job that was ticked by mistake", async () => {
    setup();
    await userEvent.click(await screen.findByLabelText("Complete Water the beans"));
    await userEvent.click(await screen.findByLabelText("Reopen Water the beans"));
    await waitFor(() => expect(post.mock.calls.some((c) => String(c[0]).endsWith("/reopen"))).toBe(true));
    expect(screen.getByLabelText("Complete Water the beans")).not.toBeChecked();
  });

  it("still prints an empty box for every job, and gives a viewer no tick boxes", async () => {
    setup("viewer");
    await screen.findByText("Water the beans");
    expect(document.querySelectorAll(".sheet-tasks .box")).toHaveLength(2);
    expect(screen.queryByLabelText("Complete Water the beans")).not.toBeInTheDocument();
  });

  it("lists the equipment the jobs need, once, and on each job", async () => {
    const spade = { id: 1, name: "Border spade", kind: "spade", kind_label: "Spade", quantity: 1, status: "in_service" };
    const fork = { id: 2, name: "Fork", kind: "fork", kind_label: "Fork", quantity: 1, status: "in_service" };
    open = [task(1, { title: "Dig the bed", feature_id: 5, equipment: [spade, fork] }), task(2, { title: "Turn the compost", tray_id: 7, equipment: [fork] })];
    setup();
    expect((await screen.findByText(/Take with you:/)).closest("p")).toHaveTextContent("Take with you: Border spade, Fork");
    expect(screen.getByText("🔧 Border spade, Fork")).toBeInTheDocument();
    expect(screen.getByText("🔧 Fork")).toBeInTheDocument();
  });

  it("says nothing about equipment when no job needs any", async () => {
    setup();
    await screen.findByText("Water the beans");
    expect(screen.queryByText(/Take with you/)).not.toBeInTheDocument();
  });
});
