import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
const patch = vi.fn();
const post = vi.fn();
vi.mock("../api/client", () => ({
  api: {
    GET: (...a: unknown[]) => get(...a),
    PATCH: (...a: unknown[]) => patch(...a),
    POST: (...a: unknown[]) => post(...a),
    DELETE: vi.fn(),
  },
  authHeader: async () => null,
  sessionRejected: vi.fn(),
}));

import TrayPage from "./TrayPage";
import TraysPage from "./TraysPage";

const counts = { empty: 9, sown: 2, germinated: 1, failed: 0, planted_out: 0 };
const tray = {
  id: 3,
  name: "Greenhouse 1",
  rows: 3,
  cols: 4,
  tray_type: "12-cell",
  location: "left shelf",
  notes: "",
  status: "active",
  sown_on: "2026-03-01",
  updated_at: "2026-03-02T10:00:00Z",
  counts,
  kinds: [{ packet_id: 7, name: "Tomato", variety: "Moneymaker", cells: 3, seeds: 5 }],
  cells: [
    { row: 0, col: 0, packet_id: 7, count: 2, status: "sown" },
    { row: 0, col: 1, packet_id: 7, count: 2, status: "sown" },
    { row: 0, col: 2, packet_id: 7, count: 1, status: "germinated" },
  ],
  photos: [],
};
const packet = { id: 7, name: "Tomato", variety: "Moneymaker" };

function setup(role: "owner" | "viewer", url: string) {
  const context = { id: 1, allotment: { id: 1, name: "Plot", role }, canEdit: role !== "viewer" };
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/a" element={<Outlet context={context} />}>
            <Route path="trays" element={<TraysPage />} />
            <Route path="trays/:trayId" element={<TrayPage />} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  get.mockReset();
  patch.mockReset();
  post.mockReset();
  get.mockImplementation(async (path: string) => {
    if (path.endsWith("/trays/{tray_id}")) return { data: tray };
    if (path.endsWith("/trays")) return { data: [tray] };
    return { data: [packet] };
  });
});

describe("Trays page", () => {
  it("lists trays with what is sown", async () => {
    setup("owner", "/a/trays");
    expect(await screen.findByText("Greenhouse 1")).toBeInTheDocument();
    expect(screen.getByText("2 sown, 1 germinated, 9 empty")).toBeInTheDocument();
    expect(screen.getByText(/3 × 4 · 12-cell · left shelf/)).toBeInTheDocument();
  });

  it("shows a thumbnail of the tray's photo, or a seedling when it has none", async () => {
    get.mockImplementation(async () => ({ data: [{ ...tray, thumb_url: "/api/v1/media/9/thumb?t=x" }, { ...tray, id: 4, name: "Bare tray", thumb_url: null }] }));
    setup("owner", "/a/trays");
    const pictured = (await screen.findByText("Greenhouse 1")).closest("a")!;
    expect(pictured.querySelector("img.packet-thumb")).toHaveAttribute("src", "/api/v1/media/9/thumb?t=x");
    expect(screen.getByText("Bare tray").closest("a")!.querySelector("img")).toBeNull();
    expect(screen.getByText("Bare tray").closest("a")!.querySelector(".packet-thumb.none")).not.toBeNull();
  });

  it("adds a tray from the form", async () => {
    post.mockResolvedValue({ data: { ...tray, id: 4 } });
    setup("owner", "/a/trays");
    await userEvent.type(await screen.findByLabelText("Name"), "Window sill");
    await userEvent.click(screen.getByRole("button", { name: "Add tray" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({ body: { name: "Window sill", rows: 4, cols: 6, tray_type: "", sown_on: null } })),
    );
  });

  it("gives viewers no add form", async () => {
    setup("viewer", "/a/trays");
    await screen.findByText("Greenhouse 1");
    expect(screen.queryByRole("button", { name: "Add tray" })).not.toBeInTheDocument();
  });
});

describe("Tray page", () => {
  it("draws the grid with each cell's state", async () => {
    setup("owner", "/a/trays/3");
    expect(await screen.findByRole("button", { name: "Row 1, column 3: Tomato (Moneymaker), germinated" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Row 3, column 4: empty" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /^Row \d, column \d:/ })).toHaveLength(12);
  });

  it("sows the selected cells with the chosen packet", async () => {
    patch.mockResolvedValue({ data: tray });
    setup("owner", "/a/trays/3");
    await userEvent.click(await screen.findByRole("button", { name: "Row 2, column 1: empty" }));
    await userEvent.click(screen.getByRole("button", { name: "Row 2, column 2: empty" }));
    expect(screen.getByText("selected", { exact: false }).textContent).toContain("2");
    await userEvent.selectOptions(screen.getByLabelText("Seed"), "7");
    await userEvent.clear(screen.getByLabelText("Seeds per cell"));
    await userEvent.type(screen.getByLabelText("Seeds per cell"), "3");
    await userEvent.click(screen.getByRole("button", { name: "Sow" }));
    await waitFor(() => expect(patch).toHaveBeenCalled());
    expect(patch.mock.calls[0][1].body).toEqual({
      cells: [{ row: 1, col: 0 }, { row: 1, col: 1 }],
      set: { packet_id: 7, count: 3 },
    });
  });

  it("edits just the seed count of cells already sown", async () => {
    patch.mockResolvedValue({ data: tray });
    setup("owner", "/a/trays/3");
    await userEvent.click(await screen.findByRole("button", { name: "Row 1, column 1: Tomato (Moneymaker), sown" }));
    await userEvent.click(screen.getByRole("button", { name: "Row 1, column 2: Tomato (Moneymaker), sown" }));
    expect(screen.getByText(/Picked: 2 with Tomato \(Moneymaker\)/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sow / update" })).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Seeds per cell"), "4");
    await userEvent.click(screen.getByRole("button", { name: "Sow / update" }));
    await waitFor(() => expect(patch).toHaveBeenCalled());
    expect(patch.mock.calls[0][1].body.set).toEqual({ count: 4 });
    expect(await screen.findByRole("status")).toHaveTextContent("Updated 2 cells");
  });

  it("changes the sown date and note of sown cells without touching the seed", async () => {
    patch.mockResolvedValue({ data: tray });
    setup("owner", "/a/trays/3");
    await userEvent.click(await screen.findByRole("button", { name: "Row 1, column 1: Tomato (Moneymaker), sown" }));
    await userEvent.type(within(screen.getByRole("region", { name: "Change the selected cells" })).getByLabelText("Sown on"), "2026-02-20");
    await userEvent.type(screen.getByLabelText("Note for these cells"), "moved to the sill");
    await userEvent.click(screen.getByRole("button", { name: "Sow / update" }));
    await waitFor(() => expect(patch).toHaveBeenCalled());
    expect(patch.mock.calls[0][1].body.set).toEqual({ sown_on: "2026-02-20", note: "moved to the sill" });
  });

  it("still needs a seed to sow into an empty cell", async () => {
    setup("owner", "/a/trays/3");
    await userEvent.click(await screen.findByRole("button", { name: "Row 3, column 4: empty" }));
    await userEvent.type(screen.getByLabelText("Seeds per cell"), "2");
    expect(screen.getByRole("button", { name: "Sow" })).toBeDisabled();
    await userEvent.selectOptions(screen.getByLabelText("Seed"), "7");
    expect(screen.getByRole("button", { name: "Sow" })).toBeEnabled();
  });

  it("picks a whole row and marks it as come up", async () => {
    patch.mockResolvedValue({ data: tray });
    setup("owner", "/a/trays/3");
    await userEvent.click(await screen.findByRole("button", { name: "Select row 1" }));
    await userEvent.click(screen.getByRole("button", { name: /Came up/ }));
    await waitFor(() => expect(patch).toHaveBeenCalled());
    const body = patch.mock.calls[0][1].body;
    expect(body.cells).toHaveLength(4);
    expect(body.set).toEqual({ status: "germinated" });
  });

  it("shows the server's refusal and keeps the selection", async () => {
    patch.mockResolvedValue({ error: { message: "Row 3, column 4: nothing is sown there" } });
    setup("owner", "/a/trays/3");
    await userEvent.click(await screen.findByRole("button", { name: "Row 3, column 4: empty" }));
    await userEvent.click(screen.getByRole("button", { name: /Failed/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("nothing is sown there");
    expect(screen.getByRole("button", { name: "Row 3, column 4: empty" })).toHaveAttribute("aria-pressed", "true");
  });

  it("warns before a smaller size cuts off selected cells, then clears the selection", async () => {
    patch.mockResolvedValue({ data: tray });
    setup("owner", "/a/trays/3");
    await userEvent.click(await screen.findByRole("button", { name: "Row 3, column 4: empty" }));
    await userEvent.click(screen.getByRole("button", { name: "Row 1, column 1: Tomato (Moneymaker), sown" }));
    await userEvent.click(screen.getByText("Tray details"));
    await userEvent.clear(screen.getByLabelText("Columns"));
    await userEvent.type(screen.getByLabelText("Columns"), "2");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("no room for 1 of the 2 selected cells");
    expect(patch).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Save and clear selection" }));
    await waitFor(() => expect(patch).toHaveBeenCalled());
    expect(patch.mock.calls[0][1].body).toMatchObject({ rows: 3, cols: 2 });
    await waitFor(() => expect(screen.getByText("selected", { exact: false }).textContent).toContain("0"));
  });

  it("saves a smaller size straight away when no selected cell is cut off", async () => {
    patch.mockResolvedValue({ data: tray });
    setup("owner", "/a/trays/3");
    await userEvent.click(await screen.findByRole("button", { name: "Row 1, column 1: Tomato (Moneymaker), sown" }));
    await userEvent.click(screen.getByText("Tray details"));
    await userEvent.clear(screen.getByLabelText("Columns"));
    await userEvent.type(screen.getByLabelText("Columns"), "2");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(patch).toHaveBeenCalled());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("lets viewers look but not change", async () => {
    setup("viewer", "/a/trays/3");
    await screen.findByRole("table");
    expect(screen.queryByRole("button", { name: "Sow" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Row 1, column 1: Tomato (Moneymaker), sown" })).toBeDisabled();
  });
});
