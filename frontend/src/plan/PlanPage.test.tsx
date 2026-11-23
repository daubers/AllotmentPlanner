import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
const post = vi.fn();
const patch = vi.fn();
vi.mock("../api/client", () => ({
  api: { GET: (...a: unknown[]) => get(...a), POST: (...a: unknown[]) => post(...a), PATCH: (...a: unknown[]) => patch(...a), DELETE: vi.fn() },
  authHeader: async () => null,
  sessionRejected: vi.fn(),
}));

import PlanPage from "./PlanPage";

const lettuce = {
  key: "lettuce", name: "Lettuce", family: "Asteraceae", category: "salad", method_default: "direct_sow", spacing_plant_cm: 30, spacing_row_cm: 30,
  germinate_days: 7, maturity_days_min: 50, maturity_days_max: 70, sow_depth_mm: 10, sow_months: [3, 4, 5, 6, 7, 8], plant_out_months: [],
  harvest_months: [5, 6, 7, 8, 9, 10], succession_days: 14, notes: "",
};
const item = (id: number, name: string, area: number, sow: string, end: string, extra = {}) => ({
  id, feature_id: 5, crop_key: "lettuce", packet_id: null, name, method: "direct_sow", area_m2: area, plant_count: null, sow_on: sow, plant_out_on: null,
  end_on: end, series_key: null, notes: "", status: "planned", planting_id: null, ...extra,
});
const planned = {
  from: "2026-03-01", to: "2027-02-28",
  beds: [
    {
      feature_id: 5, name: "Bed 1", area_m2: 100,
      items: [item(1, "Lettuce", 60, "2026-04-01", "2026-07-01"), item(2, "Radish", 60, "2026-05-01", "2026-06-01")],
      conflicts: [{ from: "2026-05-01", to: "2026-06-01", used_m2: 120, over_m2: 20, item_ids: [1, 2] }],
    },
    { feature_id: 6, name: "Pot", area_m2: null, items: [], conflicts: [] },
  ],
};

function setup(url = "/a/plan?from=2026-03", role: "owner" | "viewer" = "owner") {
  const context = { id: 1, allotment: { id: 1, name: "Plot", role }, canEdit: role !== "viewer" };
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/a" element={<Outlet context={context} />}>
            <Route path="plan" element={<PlanPage />} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  for (const m of [get, post, patch]) m.mockReset();
  get.mockImplementation(async (p: string) => {
    if (p.endsWith("/plan")) return { data: planned };
    if (p.endsWith("/crops")) return { data: [lettuce] };
    if (p.endsWith("/packets")) return { data: [] };
    return { data: [] };
  });
  post.mockResolvedValue({ data: item(9, "Lettuce", 1.8, "2026-03-01", "2026-05-10") });
  patch.mockResolvedValue({ data: item(1, "Lettuce", 60, "2026-04-01", "2026-07-01", { status: "done" }) });
});

afterEach(() => vi.useRealTimers());

describe("Plan page", () => {
  it("shows each bed with its crops, space and any overbooking", async () => {
    setup();
    const bed = await screen.findByRole("region", { name: "Bed 1" });
    expect(within(bed).getByText("about 100 m²")).toBeInTheDocument();
    expect(within(bed).getByRole("status")).toHaveTextContent("Overbooked once");
    expect(within(bed).getByText(/2026-05-01 to 2026-06-01: up to 120 m² planned in 100 m² \(over by 20 m² at worst\)/)).toBeInTheDocument();
    expect(within(bed).getByRole("button", { name: /Edit Lettuce, 60 m², 1 Apr to 1 Jul/ })).toBeInTheDocument();
    expect(within(bed).getByRole("button", { name: /Edit Radish/ })).toBeInTheDocument();
    expect(within(bed).getByText("Space used")).toBeInTheDocument();
  });

  it("says when a bed has no area to check", async () => {
    setup();
    const pot = await screen.findByRole("region", { name: "Pot" });
    expect(within(pot).getByText("size unknown")).toBeInTheDocument();
    expect(within(pot).getByText(/no area drawn/)).toBeInTheDocument();
    expect(within(pot).queryByText("Space used")).not.toBeInTheDocument();
  });

  it("moves the window a month at a time and asks for those dates", async () => {
    setup();
    expect(await screen.findByText("Mar 2026 – Feb 2027")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Later" }));
    expect(await screen.findByText("Apr 2026 – Mar 2027")).toBeInTheDocument();
    await waitFor(() =>
      expect(get).toHaveBeenCalledWith(expect.stringMatching(/\/plan$/), expect.objectContaining({ params: expect.objectContaining({ query: { from: "2026-04-01", to: "2027-03-31" } }) })),
    );
    await userEvent.click(screen.getByRole("button", { name: "Earlier" }));
    await userEvent.click(screen.getByRole("button", { name: "Earlier" }));
    expect(await screen.findByText("Feb 2026 – Jan 2027")).toBeInTheDocument();
  });

  it("can show one bed", async () => {
    setup("/a/plan?from=2026-03&bed=6");
    expect(await screen.findByRole("region", { name: "Pot" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Bed 1" })).not.toBeInTheDocument();
  });

  it("adds a crop with a suggested amount of space", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 0, 10)); // sowing starts in March
    setup();
    const bed = await screen.findByRole("region", { name: "Bed 1" });
    await userEvent.click(within(bed).getByRole("button", { name: "Add crop" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.selectOptions(within(dialog).getByLabelText("Crop"), "crop:lettuce");
    expect(within(dialog).getByLabelText("Name on the plan")).toHaveValue("Lettuce");
    expect(within(dialog).getByLabelText("Sow on")).toHaveValue("2026-03-01");
    expect(within(dialog).getByLabelText("Bed free again on")).toHaveValue("2026-05-10");
    await userEvent.type(within(dialog).getByLabelText("Plants (optional)"), "20");
    expect(within(dialog).getByText(/About 1\.8 m² for 20 plants at 30 × 30 cm/)).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("button", { name: "Use 1.8 m²" }));
    expect(within(dialog).getByLabelText("Space")).toHaveValue(1.8);
    await userEvent.click(within(dialog).getByRole("button", { name: "Add to plan" }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][1].body).toMatchObject({
      feature_id: 5, crop_key: "lettuce", name: "Lettuce", method: "direct_sow", area_m2: 1.8, plant_count: 20,
      sow_on: "2026-03-01", plant_out_on: null, end_on: "2026-05-10",
    });
  });

  it("takes the space as a share of the bed", async () => {
    setup();
    const bed = await screen.findByRole("region", { name: "Bed 1" });
    await userEvent.click(within(bed).getByRole("button", { name: "Add crop" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.selectOptions(within(dialog).getByLabelText("Crop"), "crop:lettuce");
    await userEvent.selectOptions(within(dialog).getByLabelText("Unit"), "pct");
    await userEvent.type(within(dialog).getByLabelText("Space"), "25");
    await userEvent.click(within(dialog).getByRole("button", { name: "Add to plan" }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][1].body.area_m2).toBe(25); // 25% of 100 m²
  });

  it("will not take a share of a bed with no area", async () => {
    setup();
    const pot = await screen.findByRole("region", { name: "Pot" });
    await userEvent.click(within(pot).getByRole("button", { name: "Add crop" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByRole("option", { name: "% of the bed" })).toBeDisabled();
  });

  it("repeats a crop as a succession", async () => {
    setup();
    const bed = await screen.findByRole("region", { name: "Bed 1" });
    await userEvent.click(within(bed).getByRole("button", { name: "Add crop" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.selectOptions(within(dialog).getByLabelText("Crop"), "crop:lettuce");
    await userEvent.type(within(dialog).getByLabelText("Space"), "2");
    await userEvent.click(within(dialog).getByLabelText("Repeat as a succession"));
    expect(within(dialog).getByLabelText("Every (days)")).toHaveValue(14); // the crop's usual gap
    expect(within(dialog).getByText(/Sowings: .*\d+ \w{3}, .*\d+ \w{3}/)).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("button", { name: "Add succession" }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][0]).toMatch(/plan-items\/successions$/);
    expect(post.mock.calls[0][1].body).toMatchObject({ interval_days: 14, count: 4, item: { area_m2: 2, crop_key: "lettuce" } });
  });

  it("edits an item from its bar", async () => {
    setup();
    const bed = await screen.findByRole("region", { name: "Bed 1" });
    await userEvent.click(within(bed).getByRole("button", { name: /Edit Lettuce/ }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.selectOptions(within(dialog).getByLabelText("Status"), "done");
    await userEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(patch).toHaveBeenCalled());
    expect(patch.mock.calls[0][1]).toMatchObject({ params: { path: { allotment_id: 1, item_id: 1 } }, body: { status: "done", area_m2: 60 } });
  });

  it("shows server problems in the dialog", async () => {
    post.mockResolvedValue({ error: { message: "A transplant needs a plant-out date" } });
    setup();
    const bed = await screen.findByRole("region", { name: "Bed 1" });
    await userEvent.click(within(bed).getByRole("button", { name: "Add crop" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.selectOptions(within(dialog).getByLabelText("Crop"), "crop:lettuce");
    await userEvent.type(within(dialog).getByLabelText("Space"), "2");
    await userEvent.click(within(dialog).getByRole("button", { name: "Add to plan" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("A transplant needs a plant-out date");
  });

  it("is read-only for a viewer", async () => {
    setup("/a/plan?from=2026-03", "viewer");
    const bed = await screen.findByRole("region", { name: "Bed 1" });
    expect(within(bed).queryByRole("button", { name: "Add crop" })).not.toBeInTheDocument();
    await userEvent.click(within(bed).getByRole("button", { name: /Edit Lettuce/ }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
