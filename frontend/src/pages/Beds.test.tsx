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
vi.mock("../media/hooks", () => ({
  uploadMedia: vi.fn(),
  useMedia: () => ({ data: [] }),
  useMediaActions: () => ({ refresh: vi.fn(), remove: { mutate: vi.fn() } }),
}));

import BedPage from "./BedPage";
import BedsPage from "./BedsPage";

const LAT = 51;
const DLAT = 1 / 111_320;
const DLON = 1 / (111_320 * Math.cos((LAT * Math.PI) / 180));
const poly = (x0: number, y0: number, x1: number, y1: number) => ({
  type: "Polygon",
  coordinates: [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]].map(([x, y]) => [-1 + x * DLON, LAT + y * DLAT])],
});
const bed = { id: 5, geometry: poly(0, 0, 40, 12), properties: { name: "Bed 1", kind: "bed" } };
const path = { id: 6, geometry: { type: "LineString", coordinates: [[-1, 51], [-0.999, 51]] }, properties: { name: "Path", kind: "path" } };
const carrots = {
  id: 3, feature_id: 5, bed_name: "Bed 1", packet_id: 7, packet_name: "Carrot", packet_variety: "Nantes", region: poly(2, 2, 10, 8),
  area_m2: 48, count: 40, method: "direct_sow", status: "sown", sown_on: "2026-04-02", planted_on: null, harvested_on: null, notes: "", warnings: [],
  updated_at: "2026-04-02T10:00:00Z",
};
const packet = { id: 7, name: "Carrot", variety: "Nantes", status: "active" };

function setup(url: string, role: "owner" | "viewer" = "owner") {
  const context = { id: 1, allotment: { id: 1, name: "Plot", role }, canEdit: role !== "viewer" };
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/a" element={<Outlet context={context} />}>
            <Route path="beds" element={<BedsPage />} />
            <Route path="beds/:featureId" element={<BedPage />} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  for (const m of [get, post, patch]) m.mockReset();
  get.mockImplementation(async (p: string) => {
    if (p.endsWith("/features")) return { data: { features: [bed, path] } };
    if (p.endsWith("/plantings")) return { data: [carrots] };
    if (p.endsWith("/packets")) return { data: [packet] };
    return { data: [] };
  });
});

describe("Beds page", () => {
  it("lists only areas drawn as beds, with what is growing", async () => {
    setup("/a/beds");
    expect(await screen.findByText("Bed 1")).toBeInTheDocument();
    expect(screen.queryByText("Path")).not.toBeInTheDocument();
    expect(screen.getByText("1 growing")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Bed 1/ })).toHaveAttribute("href", "/a/beds/5");
  });

  it("says what to do when there are no beds", async () => {
    get.mockImplementation(async (p: string) => (p.endsWith("/features") ? { data: { features: [path] } } : { data: [] }));
    setup("/a/beds");
    expect(await screen.findByText(/No beds yet/)).toBeInTheDocument();
  });
});

describe("Bed page", () => {
  it("draws the bed and lists its plantings", async () => {
    setup("/a/beds/5");
    expect(await screen.findByRole("img", { name: /Sketch of Bed 1/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Carrot \(Nantes\)/ })).toBeInTheDocument();
    expect(screen.getAllByText("Sown").length).toBeGreaterThan(0);
  });

  it("needs a drawn area before a planting can be added, then sends the region", async () => {
    post.mockResolvedValue({ data: { ...carrots, id: 9, warnings: ["Overlaps Carrot (Nantes) by 3 m²"] } });
    setup("/a/beds/5");
    const sketch = await screen.findByRole("img", { name: /Click the corners/ });
    const add = screen.getByRole("button", { name: "Add planting" });
    expect(add).toBeDisabled();
    // the sketch is 640 x 360 in a jsdom box of 0 x 0, so click through "Whole bed" instead
    await userEvent.click(screen.getByRole("button", { name: "Whole bed" }));
    expect(sketch).toBeInTheDocument();
    expect(add).toBeEnabled();
    await userEvent.selectOptions(screen.getByLabelText("Seed"), "7");
    await userEvent.type(screen.getByLabelText("Seeds or plants"), "30");
    await userEvent.click(add);
    await waitFor(() => expect(post).toHaveBeenCalled());
    const body = post.mock.calls[0][1].body;
    expect(body).toMatchObject({ feature_id: 5, packet_id: 7, count: 30 });
    expect(body.region.type).toBe("Polygon");
    expect(body.region.coordinates[0]).toHaveLength(5);
    expect(await screen.findByText("Overlaps Carrot (Nantes) by 3 m²")).toBeInTheDocument();
  });

  it("shows the server's refusal", async () => {
    post.mockResolvedValue({ error: { message: "The planting region goes outside the bed" } });
    setup("/a/beds/5");
    await userEvent.click(await screen.findByRole("button", { name: "Whole bed" }));
    await userEvent.click(screen.getByRole("button", { name: "Add planting" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("outside the bed");
  });

  it("opens a planting to change its state", async () => {
    patch.mockResolvedValue({ data: { ...carrots, status: "growing" } });
    setup("/a/beds/5");
    await userEvent.click(await screen.findByRole("button", { name: /Carrot \(Nantes\)/ }));
    await userEvent.selectOptions(screen.getByLabelText("State"), "growing");
    await userEvent.click(within(screen.getByRole("region", { name: "Plantings" })).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(patch).toHaveBeenCalled());
    expect(patch.mock.calls[0][1].body).toMatchObject({ status: "growing", count: 40 });
  });

  it("lets viewers look but not change", async () => {
    setup("/a/beds/5", "viewer");
    await screen.findByRole("img", { name: /Sketch of Bed 1/ });
    expect(screen.queryByRole("button", { name: "Add planting" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Whole bed" })).not.toBeInTheDocument();
  });

  it("says when the bed does not exist", async () => {
    setup("/a/beds/99");
    expect(await screen.findByText(/Bed not found/)).toBeInTheDocument();
  });

describe("Planting from the plan", () => {
  const item = (extra = {}) => ({
    id: 7, feature_id: 5, crop_key: "lettuce", packet_id: 7, name: "Carrot", method: "direct_sow", area_m2: 12, plant_count: 120,
    sow_on: "2026-04-01", plant_out_on: null, end_on: "2026-07-01", series_key: null, notes: "from the plan", status: "planned", planting_id: null, ...extra,
  });
  const withItem = (it: object) =>
    get.mockImplementation(async (p: string) => {
      if (p.endsWith("/plan-items/{item_id}")) return { data: it };
      if (p.endsWith("/features")) return { data: { features: [bed, path] } };
      if (p.endsWith("/plantings")) return { data: [carrots] };
      if (p.endsWith("/packets")) return { data: [packet] };
      return { data: [] };
    });

  it("prefills the form from the planned crop and says it will be marked done", async () => {
    withItem(item());
    post.mockResolvedValue({ data: { ...carrots, id: 9, warnings: [] } });
    setup("/a/beds/5?planItem=7");
    expect(await screen.findByText(/Planting from your plan:/)).toHaveTextContent("Planting from your plan: Carrot, about 12 m² for 120 plants");
    expect(screen.getByLabelText("Seed")).toHaveValue("7");
    expect(screen.getByLabelText("Seeds or plants")).toHaveValue(120);
    expect(screen.getByLabelText("Notes")).toHaveValue("from the plan");
    await userEvent.click(screen.getByRole("button", { name: "Whole bed" }));
    await userEvent.click(screen.getByRole("button", { name: "Add planting" }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][1].body).toMatchObject({ feature_id: 5, packet_id: 7, count: 120, plan_item_id: 7 });
    await waitFor(() => expect(screen.queryByText(/Planting from your plan/)).not.toBeInTheDocument());
  });

  it("does not link a planting to a plan item for another bed", async () => {
    withItem(item({ feature_id: 6 }));
    post.mockResolvedValue({ data: { ...carrots, id: 9, warnings: [] } });
    setup("/a/beds/5?planItem=7");
    await screen.findByRole("button", { name: "Whole bed" });
    expect(screen.queryByText(/Planting from your plan/)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Whole bed" }));
    await userEvent.click(screen.getByRole("button", { name: "Add planting" }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][1].body.plan_item_id).toBeNull();
  });

  it("ignores a plan item that has already been planted", async () => {
    withItem(item({ status: "done", planting_id: 3 }));
    setup("/a/beds/5?planItem=7");
    await screen.findByRole("button", { name: "Whole bed" });
    expect(screen.queryByText(/Planting from your plan/)).not.toBeInTheDocument();
    expect(screen.getByLabelText("Seeds or plants")).toHaveValue(null);
  });
});
});
