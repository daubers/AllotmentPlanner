import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
vi.mock("../api/client", () => ({ api: { GET: (...a: unknown[]) => get(...a) } }));

import AllotmentLayout from "./AllotmentLayout";

function visit(path: string, role = "owner") {
  get.mockResolvedValue({ data: { id: 1, name: "Plot 12", role } });
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/allotments/:id" element={<AllotmentLayout />}>
            <Route index element={<p>the map</p>} />
            <Route path="*" element={<p>a page</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const groups = () => within(screen.getByRole("navigation", { name: "Sections" }));
const labels = (nav: HTMLElement) => within(nav).getAllByRole("link").map((a) => a.textContent);

describe("allotment menu", () => {
  beforeEach(() => get.mockReset());

  it("shows the four groups, and the pages of the one you are in", async () => {
    visit("/allotments/1");
    await screen.findByText("Plot 12");
    expect(groups().getAllByRole("link").map((a) => a.textContent)).toEqual(["Plot", "Grow", "Work", "Record"]);
    expect(labels(screen.getByRole("navigation", { name: "Plot pages" }))).toEqual(["Map", "Map from photos"]);
    expect(screen.queryByRole("navigation", { name: "Grow pages" })).not.toBeInTheDocument();
  });

  it("marks the current group, and keeps it for a detail page", async () => {
    visit("/allotments/1/beds/5");
    await screen.findByText("Plot 12");
    expect(groups().getByRole("link", { name: "Grow" })).toHaveClass("active");
    expect(groups().getByRole("link", { name: "Plot" })).not.toHaveClass("active");
    expect(labels(screen.getByRole("navigation", { name: "Grow pages" }))).toEqual(["Seeds", "Trays", "Beds", "Plan", "Equipment"]);
    expect(within(screen.getByRole("navigation", { name: "Grow pages" })).getByRole("link", { name: "Beds" })).toHaveClass("active");
  });

  it("sends each group to its first page, and Map from photos to /layers", async () => {
    visit("/allotments/1/layers");
    await screen.findByText("Plot 12");
    expect(groups().getByRole("link", { name: "Work" })).toHaveAttribute("href", "/allotments/1/today");
    expect(groups().getByRole("link", { name: "Record" })).toHaveAttribute("href", "/allotments/1/photos");
    expect(screen.getByRole("link", { name: "Map from photos" })).toHaveAttribute("href", "/allotments/1/layers");
  });

  it("offers Settings to editors and owners but not viewers", async () => {
    visit("/allotments/1", "editor");
    expect(await screen.findByRole("link", { name: "Settings" })).toBeInTheDocument();
  });

  it("hides Settings from a viewer", async () => {
    visit("/allotments/1", "viewer");
    await screen.findByText("Plot 12");
    expect(screen.queryByRole("link", { name: "Settings" })).not.toBeInTheDocument();
  });

  it("shows no second row on Settings", async () => {
    visit("/allotments/1/settings");
    await screen.findByText("Plot 12");
    expect(groups().queryByRole("link", { name: "Plot", current: "page" })).not.toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: /pages$/ })).not.toBeInTheDocument();
  });
});
