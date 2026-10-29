import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
const patch = vi.fn();
const post = vi.fn();
const upload = vi.fn();
vi.mock("../api/client", () => ({
  api: { GET: (...a: unknown[]) => get(...a), PATCH: (...a: unknown[]) => patch(...a), POST: (...a: unknown[]) => post(...a), DELETE: vi.fn() },
  authHeader: async () => null,
  sessionRejected: vi.fn(),
}));
vi.mock("../media/hooks", () => ({
  uploadMedia: (...a: unknown[]) => upload(...a),
  useMediaActions: () => ({ remove: { mutate: vi.fn() } }),
}));

import PacketPage from "./PacketPage";
import SeedsPage from "./SeedsPage";

const draft = {
  id: 9,
  status: "draft",
  name: "Carrot",
  variety: "Flyaway F1",
  supplier: "Mr Fothergill's",
  stock: "full",
  sun: null,
  notes: "",
  latin_name: "",
  updated_at: "2026-10-29T10:00:00Z",
  sow_depth_mm: 15,
  best_before_year: null,
  seeds_in_packet: 500,
  calendar: { sow_outdoors: [3, 4, 5], harvest: [8, 9] },
  photos: [],
};
const scan = {
  id: 4,
  status: "ready",
  packet_id: 9,
  media_id: 1,
  calendar_source: "graphic",
  missing: ["best_before_year", "germinate_days"],
  crop: { id: 2, url: "/crop.jpg" },
  finished_at: new Date().toISOString(),
};

function setup(url: string, role: "owner" | "viewer" = "owner") {
  const context = { id: 1, allotment: { id: 1, name: "Plot", role }, canEdit: role !== "viewer" };
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
  for (const m of [get, patch, post, upload]) m.mockReset();
  get.mockImplementation(async (path: string, opts?: { params?: { query?: { status?: string } } }) => {
    if (path.endsWith("/packets/{packet_id}")) return { data: draft };
    if (path.endsWith("/packet-scans")) return { data: [scan] };
    if (opts?.params?.query?.status === "draft") return { data: [draft] };
    return { data: [] };
  });
});

describe("Seeds page: scanning", () => {
  it("lists drafts to review and links to them", async () => {
    setup("/a/seeds");
    expect(await screen.findByText("To review (1)")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Carrot/ })).toHaveAttribute("href", "/a/seeds/9");
    expect(screen.getByText("Draft")).toBeInTheDocument();
  });

  it("uploads a photo, starts reading it, and offers the draft when it is ready", async () => {
    upload.mockResolvedValue({ id: 77 });
    post.mockResolvedValue({ data: { id: 5, status: "queued" } });
    setup("/a/seeds");
    const file = new File(["x"], "back.jpg", { type: "image/jpeg" });
    await userEvent.upload(await screen.findByLabelText("Photos of packet backs"), file);
    await waitFor(() => expect(upload).toHaveBeenCalled());
    expect(upload.mock.calls[0][1]).toEqual({ file });
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(expect.stringContaining("packet-scans"), expect.objectContaining({ body: { media_id: 77 } })),
    );
    expect(await screen.findByRole("link", { name: "Review the draft" })).toHaveAttribute("href", "/a/seeds/9");
  });

  it("shows why an upload failed", async () => {
    upload.mockRejectedValue(new Error("back.jpg is 5 GB, but the largest upload allowed is 4 GB"));
    setup("/a/seeds");
    await userEvent.upload(await screen.findByLabelText("Photos of packet backs"), new File(["x"], "back.jpg", { type: "image/jpeg" }));
    expect(await screen.findByText(/largest upload allowed/)).toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();
  });

  it("offers a retry for a scan that failed", async () => {
    get.mockImplementation(async (path: string) => {
      if (path.endsWith("/packet-scans")) return { data: [{ id: 6, status: "failed", error: "Could not read the photo: RuntimeError", missing: [] }] };
      return { data: [] };
    });
    post.mockResolvedValue({ data: { id: 6, status: "queued" } });
    setup("/a/seeds");
    expect(await screen.findByText(/Could not read the photo/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(post).toHaveBeenCalledWith(expect.stringContaining("/retry"), expect.anything()));
  });

  it("gives viewers no scan button", async () => {
    setup("/a/seeds", "viewer");
    await screen.findByText("To review (1)");
    expect(screen.queryByLabelText("Photos of packet backs")).not.toBeInTheDocument();
  });
});

describe("Packet page: reviewing a draft", () => {
  it("says it was read from a photo, shows the calendar as read, and marks what was not found", async () => {
    setup("/a/seeds/9");
    expect(await screen.findByText(/Read from a photo/)).toBeInTheDocument();
    expect(screen.getByAltText("The calendar as read from your photo")).toHaveAttribute("src", "/crop.jpg");
    expect(screen.getByLabelText(/Best before/).closest("label")).toHaveClass("missing");
    expect(screen.getByLabelText("Name").closest("label")).not.toHaveClass("missing");
    expect(screen.getByLabelText("Seeds in the packet")).toHaveValue(500);
  });

  it("saving a draft adds it to the library", async () => {
    patch.mockResolvedValue({ data: { ...draft, status: "active" } });
    setup("/a/seeds/9");
    await userEvent.click(await screen.findByRole("button", { name: "Save to library" }));
    await waitFor(() => expect(patch).toHaveBeenCalled());
    const body = patch.mock.calls[0][1].body;
    expect(body.status).toBe("active");
    expect(body.seeds_in_packet).toBe(500);
    expect(body.calendar).toEqual({ sow_outdoors: [3, 4, 5], harvest: [8, 9] });
  });

  it("a normal packet shows no draft banner and a plain Save", async () => {
    get.mockImplementation(async (path: string) =>
      path.endsWith("/packets/{packet_id}") ? { data: { ...draft, status: "active" } } : { data: [] },
    );
    setup("/a/seeds/9");
    expect(await screen.findByRole("button", { name: "Save" })).toBeInTheDocument();
    expect(screen.queryByText(/Read from a photo/)).not.toBeInTheDocument();
  });
});
