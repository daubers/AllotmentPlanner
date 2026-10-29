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

import TrayPage from "./TrayPage";

const LAT = 51;
const DLAT = 1 / 111_320;
const DLON = 1 / (111_320 * Math.cos((LAT * Math.PI) / 180));
const bed = {
  id: 5,
  geometry: { type: "Polygon", coordinates: [[[0, 0], [30, 0], [30, 10], [0, 10], [0, 0]].map(([x, y]) => [-1 + x * DLON, LAT + y * DLAT])] },
  properties: { name: "Bed 1", kind: "bed" },
};
const tray = {
  id: 3, name: "Greenhouse 1", rows: 2, cols: 3, tray_type: "", location: "", notes: "", status: "active", sown_on: "2026-03-01",
  updated_at: "2026-03-02T10:00:00Z",
  counts: { empty: 4, sown: 0, germinated: 2, failed: 0, planted_out: 0 },
  kinds: [{ packet_id: 7, name: "Tomato", variety: "", cells: 2, seeds: 2 }],
  cells: [
    { row: 0, col: 0, packet_id: 7, count: 1, status: "germinated" },
    { row: 0, col: 1, packet_id: 7, count: 1, status: "germinated" },
  ],
  photos: [],
};

function setup(role: "owner" | "viewer" = "owner") {
  const context = { id: 1, allotment: { id: 1, name: "Plot", role }, canEdit: role !== "viewer" };
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={["/a/trays/3"]}>
        <Routes>
          <Route path="/a" element={<Outlet context={context} />}>
            <Route path="trays/:trayId" element={<TrayPage />} />
            <Route path="beds/:featureId" element={<p>The bed page</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  get.mockReset();
  post.mockReset();
  get.mockImplementation(async (p: string) => {
    if (p.endsWith("/trays/{tray_id}")) return { data: tray };
    if (p.endsWith("/features")) return { data: { features: [bed] } };
    return { data: [] };
  });
});

describe("Planting out from a tray", () => {
  it("offers to plant out once cells are chosen, and sends the cells, bed and drawn region", async () => {
    post.mockResolvedValue({ data: { plantings: [], tray } });
    setup();
    expect(screen.queryByText(/Plant out \d/)).not.toBeInTheDocument();
    await userEvent.click(await screen.findByRole("button", { name: /Row 1, column 1: Tomato, germinated/ }));
    await userEvent.click(screen.getByRole("button", { name: /Row 1, column 2: Tomato, germinated/ }));
    expect(await screen.findByText("Plant out 2 cells")).toBeInTheDocument();
    const submit = screen.getByRole("button", { name: "Plant out" });
    expect(submit).toBeDisabled();
    await userEvent.selectOptions(screen.getByLabelText("Into which bed"), "5");
    await userEvent.click(await screen.findByRole("button", { name: "Whole bed" }));
    expect(submit).toBeEnabled();
    await userEvent.click(submit);
    await waitFor(() => expect(post).toHaveBeenCalled());
    const body = post.mock.calls[0][1].body;
    expect(body.cells).toEqual([{ row: 0, col: 0 }, { row: 0, col: 1 }]);
    expect(body.feature_id).toBe(5);
    expect(body.region.type).toBe("Polygon");
    expect(await screen.findByText("The bed page")).toBeInTheDocument();
  });

  it("shows why the server refused", async () => {
    post.mockResolvedValue({ error: { message: "Row 1, column 2: did not come up" } });
    setup();
    await userEvent.click(await screen.findByRole("button", { name: /Row 1, column 1: Tomato, germinated/ }));
    await userEvent.selectOptions(await screen.findByLabelText("Into which bed"), "5");
    await userEvent.click(await screen.findByRole("button", { name: "Whole bed" }));
    await userEvent.click(screen.getByRole("button", { name: "Plant out" }));
    expect(await screen.findByText(/did not come up/)).toBeInTheDocument();
  });

  it("gives viewers no plant-out panel", async () => {
    setup("viewer");
    await screen.findByRole("table");
    expect(screen.queryByText(/Plant out \d/)).not.toBeInTheDocument();
  });
});
