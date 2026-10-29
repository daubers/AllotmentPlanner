import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
const post = vi.fn();
vi.mock("../api/client", () => ({
  api: { GET: (...a: unknown[]) => get(...a), POST: (...a: unknown[]) => post(...a), PATCH: vi.fn(), DELETE: vi.fn() },
  authHeader: async () => "Bearer t",
  sessionRejected: vi.fn(),
}));

import LayersPage from "./LayersPage";

const photos = Array.from({ length: 6 }, (_, i) => ({ id: i + 1, kind: "photo", status: "ready", filename: `p${i}.jpg`, lat: 51.5, lng: -0.12 }));
const outline = {
  polygon: { type: "Polygon", coordinates: [[[-0.12, 51.5], [-0.1197, 51.5], [-0.1197, 51.5002], [-0.12, 51.5002], [-0.12, 51.5]]] },
  area_m2: 412.4, perimeter_m: 81.2, gap_m: 0.4, points_in: 120, points_out: 5, warnings: ["Few points: a trace recorded every second follows the edge more closely"],
};
const file = () => new File(["<gpx/>"], "plot.gpx", { type: "application/gpx+xml" });

function setup() {
  const context = { id: 1, allotment: { id: 1, name: "Plot", role: "owner" }, canEdit: true };
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={["/a/layers"]}>
        <Routes>
          <Route path="/a" element={<Outlet context={context} />}>
            <Route path="layers" element={<LayersPage />} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  get.mockReset();
  post.mockReset();
  get.mockImplementation(async (p: string) => (p.endsWith("/media") ? { data: photos } : { data: [] }));
  post.mockResolvedValue({ data: { id: 9, status: "queued" } });
});
afterEach(() => vi.unstubAllGlobals());

const reply = (ok: boolean, body: unknown) => vi.fn(async (_url: string, _init?: RequestInit) => ({ ok, json: async () => body }));

describe("Plot boundary from a GPX trace", () => {
  it("reads the file on the server, shows the outline and warnings, and sends it with the build", async () => {
    const fetchMock = reply(true, outline);
    vi.stubGlobal("fetch", fetchMock);
    setup();
    await userEvent.upload(await screen.findByLabelText("GPX file"), file());
    expect(await screen.findByText(/Outline found: 412 m², 81 m round, 5 corners/)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "The outline the trace gives" })).toBeInTheDocument();
    expect(screen.getByText(/Few points/)).toBeInTheDocument();
    expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/allotments/1/boundary-from-gpx");
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: "POST", headers: expect.objectContaining({ Authorization: "Bearer t" }) });

    await userEvent.click(screen.getByRole("button", { name: "Start" }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][1].body.boundary).toEqual(outline.polygon);
  });

  it("shows why a file was refused and builds without a boundary", async () => {
    vi.stubGlobal("fetch", reply(false, { message: "The walk stops 60 m from where it started." }));
    setup();
    await userEvent.upload(await screen.findByLabelText("GPX file"), file());
    expect(await screen.findByRole("alert")).toHaveTextContent("stops 60 m from where it started");
    await userEvent.click(screen.getByRole("button", { name: "Start" }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][1].body.boundary).toBeNull();
  });

  it("lets you drop the trace again", async () => {
    vi.stubGlobal("fetch", reply(true, outline));
    setup();
    await userEvent.upload(await screen.findByLabelText("GPX file"), file());
    await userEvent.click(await screen.findByRole("button", { name: "Don't use it" }));
    expect(screen.queryByText(/Outline found/)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Start" }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][1].body.boundary).toBeNull();
  });

  it("offers the field only when objects are being recognised", async () => {
    setup();
    await screen.findByLabelText("GPX file");
    await userEvent.click(screen.getByLabelText(/Recognise things/));
    expect(screen.queryByLabelText("GPX file")).not.toBeInTheDocument();
  });
});
