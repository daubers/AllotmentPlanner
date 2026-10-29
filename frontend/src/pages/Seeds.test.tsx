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

import PacketPage from "./PacketPage";
import SeedsPage from "./SeedsPage";

const tomato = {
  id: 7,
  name: "Tomato",
  variety: "Moneymaker",
  supplier: "Suttons",
  stock: "low",
  sun: null,
  notes: "",
  latin_name: "",
  updated_at: "2026-10-29T10:00:00Z",
  maturity_days_min: 60,
  maturity_days_max: 90,
  calendar: { sow_indoors: [2, 3], sow_outdoors: [], plant_out: [], harvest: [8] },
  photos: [],
};

function setup(role: "owner" | "viewer", url: string) {
  const canEdit = role !== "viewer";
  const context = { id: 1, allotment: { id: 1, name: "Plot", role }, canEdit };
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/a" element={<Outlet context={context} />}>
            <Route path="seeds" element={<SeedsPage />} />
            <Route path="seeds/:packetId" element={<PacketPage />} />
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
  get.mockImplementation(async (path: string) =>
    path.endsWith("/packets/{packet_id}") ? { data: tomato } : { data: [tomato] },
  );
});

describe("Seeds page", () => {
  it("lists packets with their variety and stock", async () => {
    setup("owner", "/a/seeds");
    expect(await screen.findByText("Moneymaker · Suttons")).toBeInTheDocument();
    expect(screen.getByText("Running low", { selector: ".badge" })).toBeInTheDocument();
    expect(screen.getByText("Harvest in 60 to 90 days")).toBeInTheDocument();
  });

  it("searches and filters to what can be sown this month", async () => {
    setup("owner", "/a/seeds");
    await screen.findByText("Moneymaker · Suttons");
    await userEvent.type(screen.getByLabelText("Search seeds"), "tom");
    await waitFor(() =>
      expect(get).toHaveBeenLastCalledWith(expect.any(String), expect.objectContaining({ params: expect.objectContaining({ query: expect.objectContaining({ q: "tom" }) }) })),
    );
    await userEvent.click(screen.getByLabelText("Can sow in"));
    await waitFor(() => {
      const query = get.mock.calls.at(-1)![1].params.query;
      expect(query.month).toBe(new Date().getMonth() + 1);
    });
  });

  it("lets editors add a packet and hides that from viewers", async () => {
    post.mockResolvedValue({ data: { ...tomato, id: 9 } });
    setup("owner", "/a/seeds");
    await userEvent.type(await screen.findByLabelText("Name"), "Kale");
    await userEvent.click(screen.getByRole("button", { name: "Add packet" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({ body: { name: "Kale", variety: "", supplier: "" } })),
    );
  });

  it("gives viewers no way to add", async () => {
    setup("viewer", "/a/seeds");
    await screen.findByText("Moneymaker · Suttons");
    expect(screen.queryByRole("button", { name: "Add packet" })).not.toBeInTheDocument();
  });
});

describe("Packet page", () => {
  it("saves the months you tap", async () => {
    patch.mockResolvedValue({ data: tomato });
    setup("owner", "/a/seeds/7");
    const grid = await screen.findByRole("table");
    await userEvent.click(within(grid).getByRole("button", { name: "Sow outdoors in May" }));
    await userEvent.click(within(grid).getByRole("button", { name: "Sow indoors in Feb" })); // switch off
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(patch).toHaveBeenCalled());
    const body = patch.mock.calls[0][1].body;
    expect(body.calendar).toEqual({ sow_indoors: [3], sow_outdoors: [5], plant_out: [], harvest: [8] });
    expect(body.name).toBe("Tomato");
    expect(body.sun).toBeNull();
    expect(body.maturity_days_max).toBe(90);
  });

  it("shows the server's message when a save is refused", async () => {
    patch.mockResolvedValue({ error: { message: "Days to germinate: the minimum is more than the maximum" } });
    setup("owner", "/a/seeds/7");
    await screen.findByRole("table");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("minimum is more than the maximum");
  });

  it("is read-only for viewers", async () => {
    setup("viewer", "/a/seeds/7");
    await screen.findByRole("table");
    expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Sow indoors in/ })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Name")).toBeDisabled();
  });
});
