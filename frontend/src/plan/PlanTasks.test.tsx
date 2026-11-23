import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
const post = vi.fn();
vi.mock("../api/client", () => ({
  api: { GET: (...a: unknown[]) => get(...a), POST: (...a: unknown[]) => post(...a), PATCH: vi.fn(), DELETE: vi.fn() },
  authHeader: async () => null,
  sessionRejected: vi.fn(),
}));

import MaintenanceDialog from "./MaintenanceDialog";
import PlanTasks from "./PlanTasks";

const beds = [
  { feature_id: 5, name: "Bed 1", area_m2: 100, items: [], conflicts: [] },
  { feature_id: 6, name: "Bed 2", area_m2: 40, items: [], conflicts: [] },
];
const s = (key: string, title: string, due: string, feature: number, added = false) => ({
  key, title, description: "", due_date: due, feature_id: feature, plan_item_id: 1, added,
});
let payload: { suggestions: ReturnType<typeof s>[]; stale: number };

function wrap(ui: React.ReactElement) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{ui}</QueryClientProvider>);
}
const panel = (props: Partial<React.ComponentProps<typeof PlanTasks>> = {}) =>
  wrap(<PlanTasks allotmentId={1} beds={beds} featureId={null} canEdit onMaintenance={vi.fn()} {...props} />);

beforeEach(() => {
  for (const m of [get, post]) m.mockReset();
  payload = {
    suggestions: [
      s("plan:sow:1", "Sow Lettuce in Bed 1", "2027-03-15", 5),
      s("plan:change:1:end", "Clear Lettuce in Bed 1", "2027-05-20", 5),
      s("plan:sow:2", "Sow Garlic in Bed 2", "2026-12-01", 6),
      s("plan:sow:3", "Sow Pea in Bed 2", "2027-03-01", 6, true),
    ],
    stale: 0,
  };
  get.mockImplementation(async () => ({ data: payload }));
  post.mockResolvedValue({ data: [{ id: 1 }, { id: 2 }, { id: 3 }] });
});

describe("Tasks from the plan", () => {
  it("lists the jobs not yet made, by bed, with their dates", async () => {
    panel();
    const bed1 = await screen.findByRole("heading", { name: "Bed 1" });
    expect(bed1).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Bed 2" })).toBeInTheDocument();
    expect(screen.getByText("Sow Lettuce in Bed 1")).toBeInTheDocument();
    expect(screen.getByText(/15 Mar/)).toBeInTheDocument();
    expect(screen.queryByText("Sow Pea in Bed 2")).not.toBeInTheDocument(); // already a task
    expect(screen.getByRole("button", { name: "Add 3 tasks" })).toBeEnabled();
  });

  it("adds the ticked jobs", async () => {
    panel();
    await userEvent.click(await screen.findByRole("checkbox", { name: /Clear Lettuce in Bed 1/ }));
    expect(screen.getByRole("button", { name: "Add 2 tasks" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Add 2 tasks" }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][0]).toMatch(/\/plan\/tasks$/);
    expect(post.mock.calls[0][1].body).toEqual({ keys: ["plan:sow:1", "plan:sow:2"], feature_id: null, equipment: null });
    expect(await screen.findByRole("status")).toHaveTextContent("Added 3 tasks");
  });

  it("cannot add when everything is unticked", async () => {
    panel();
    for (const box of await screen.findAllByRole("checkbox")) await userEvent.click(box);
    expect(screen.getByRole("button", { name: "Add 0 tasks" })).toBeDisabled();
  });

  it("asks for one bed's jobs when a bed is chosen", async () => {
    panel({ featureId: 6 });
    await screen.findByText("Sow Garlic in Bed 2");
    expect(get).toHaveBeenCalledWith(
      expect.stringMatching(/plan\/task-suggestions$/),
      expect.objectContaining({ params: expect.objectContaining({ query: { feature_id: 6 } }) }),
    );
  });

  it("says when tasks have fallen out of step and updates them on request", async () => {
    payload.stale = 2;
    post.mockResolvedValue({ data: { updated: 1, removed: 1 } });
    panel();
    const note = await screen.findByText(/2 tasks made from the plan are out of date/);
    expect(note).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Update them" }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][0]).toMatch(/\/plan\/tasks\/sync$/);
    expect(await screen.findByText("Updated 1 and removed 1 tasks to match the plan.")).toBeInTheDocument();
  });

  it("uses the singular for one stale task", async () => {
    payload.stale = 1;
    panel();
    expect(await screen.findByText(/1 task made from the plan is out of date/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Update it" })).toBeInTheDocument();
  });

  it("explains an empty plan, and a fully added one", async () => {
    payload.suggestions = [];
    const { unmount } = panel();
    expect(await screen.findByText(/Nothing to add yet/)).toBeInTheDocument();
    unmount();
    payload.suggestions = [s("plan:sow:3", "Sow Pea in Bed 2", "2027-03-01", 6, true)];
    panel();
    expect(await screen.findByText("Every job from the plan is already a task.")).toBeInTheDocument();
  });

  it("shows a server problem", async () => {
    post.mockResolvedValue({ error: { message: "Not part of the plan: plan:sow:9" } });
    panel();
    await userEvent.click(await screen.findByRole("button", { name: "Add 3 tasks" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Not part of the plan");
  });

  it("is look-only for a viewer", async () => {
    payload.stale = 1;
    panel({ canEdit: false });
    await screen.findByText("Sow Lettuce in Bed 1");
    expect(screen.queryByRole("button", { name: /^Add \d/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Update it" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add a repeating job" })).not.toBeInTheDocument();
    for (const box of screen.getAllByRole("checkbox")) expect(box).toBeDisabled();
  });

  it("opens the repeating job dialog", async () => {
    const onMaintenance = vi.fn();
    panel({ onMaintenance });
    await userEvent.click(await screen.findByRole("button", { name: "Add a repeating job" }));
    expect(onMaintenance).toHaveBeenCalled();
  });
});

describe("Tasks from the plan with equipment", () => {
  const tool = (id: number, name: string) => ({ id, name, kind: "dibber", kind_label: "Dibber", quantity: 1, status: "in_service", reason: "sowing" });

  it("ticks suggested equipment and sends what stays ticked with the jobs", async () => {
    payload.suggestions = [
      { ...s("plan:sow:1", "Sow Lettuce in Bed 1", "2027-03-15", 5), equipment: [tool(7, "Dibber"), tool(8, "Labels")] } as never,
      { ...s("plan:change:1:end", "Clear Lettuce in Bed 1", "2027-05-20", 5), equipment: [] } as never,
    ];
    panel();
    await userEvent.click(await screen.findByRole("checkbox", { name: "Labels" })); // switch one off
    await userEvent.click(screen.getByRole("button", { name: "Add 2 tasks" }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][1].body).toEqual({ keys: ["plan:sow:1", "plan:change:1:end"], feature_id: null, equipment: { "plan:sow:1": [7] } });
  });

  it("does not show equipment for a job that has been unticked", async () => {
    payload.suggestions = [{ ...s("plan:sow:1", "Sow Lettuce in Bed 1", "2027-03-15", 5), equipment: [tool(7, "Dibber")] } as never];
    panel();
    await screen.findByRole("checkbox", { name: "Dibber" });
    await userEvent.click(screen.getByRole("checkbox", { name: /Sow Lettuce in Bed 1/ }));
    expect(screen.queryByRole("checkbox", { name: "Dibber" })).not.toBeInTheDocument();
  });

  it("is look-only for a viewer", async () => {
    payload.suggestions = [{ ...s("plan:sow:1", "Sow Lettuce in Bed 1", "2027-03-15", 5), equipment: [tool(7, "Dibber")] } as never];
    panel({ canEdit: false });
    expect(await screen.findByRole("checkbox", { name: "Dibber" })).toBeDisabled();
  });
});

describe("Repeating job dialog", () => {
  const open = (props: Partial<React.ComponentProps<typeof MaintenanceDialog>> = {}) => {
    const onClose = vi.fn();
    wrap(<MaintenanceDialog allotmentId={1} beds={beds} bedId={null} until="2027-02-28" onClose={onClose} {...props} />);
    return onClose;
  };

  it("makes a weekly schedule on a bed until the end of the window", async () => {
    post.mockResolvedValue({ data: { id: 3 } });
    const onClose = open({ bedId: 6 });
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByLabelText("Job")).toHaveValue("Weed Bed 2");
    expect(within(dialog).getByLabelText("Until")).toHaveValue("2027-02-28");
    await userEvent.click(within(dialog).getByRole("button", { name: "Add job" }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][0]).toMatch(/\/task-series$/);
    expect(post.mock.calls[0][1].body).toMatchObject({ title: "Weed Bed 2", feature_id: 6, every_n: 1, unit: "week", until_on: "2027-02-28" });
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it("keeps the default name pointed at the chosen bed, but not a name you wrote", async () => {
    open();
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByLabelText("Job")).toHaveValue("Weed Bed 1");
    await userEvent.selectOptions(within(dialog).getByLabelText("Bed"), "Bed 2");
    expect(within(dialog).getByLabelText("Job")).toHaveValue("Weed Bed 2");
    const job = within(dialog).getByLabelText("Job");
    await userEvent.clear(job);
    await userEvent.type(job, "Water");
    await userEvent.selectOptions(within(dialog).getByLabelText("Bed"), "Bed 1");
    expect(job).toHaveValue("Water");
  });

  it("shows the server's message", async () => {
    post.mockResolvedValue({ error: { message: "The series ends before it starts" } });
    open();
    await userEvent.click(screen.getByRole("button", { name: "Add job" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The series ends before it starts");
  });
});
