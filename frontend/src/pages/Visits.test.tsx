import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
vi.mock("../api/client", () => ({
  api: { GET: (...a: unknown[]) => get(...a), POST: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() },
  authHeader: async () => null,
  sessionRejected: vi.fn(),
  getSession: () => null,
}));

import VisitsPage from "./VisitsPage";

const tool = (id: number, name: string, source = "task") => ({ id, name, kind: null, kind_label: "Other", quantity: 1, status: "in_service", source, task_ids: [1] });
const visit = (id: number, title: string, bring: ReturnType<typeof tool>[], extra = {}) => ({
  id, title, notes: "", starts_at: "2026-11-07T09:00:00Z", duration_minutes: 90, task_ids: [1], bring, equipment_extras: [], ...extra,
});

function setup(visits: unknown[]) {
  get.mockReset();
  get.mockImplementation(async (p: string) => ({ data: p.endsWith("/visits") ? visits : [] }));
  const context = { id: 1, allotment: { id: 1, name: "Plot", role: "owner" }, canEdit: true };
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={["/a/visits"]}>
        <Routes>
          <Route path="/a" element={<Outlet context={context} />}>
            <Route path="visits" element={<VisitsPage />} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  get.mockReset();
});

describe("Visits page", () => {
  it("says what to bring on each visit", async () => {
    setup([visit(1, "Saturday", [tool(1, "Border spade"), tool(2, "Fork")]), visit(2, "Sunday", [])]);
    expect(await screen.findByText("🔧 Bring: Border spade, Fork")).toBeInTheDocument();
    expect(screen.getAllByText(/Bring:/)).toHaveLength(1); // Sunday has nothing to bring
  });

  it("shortens a long list", async () => {
    setup([visit(1, "Big day", ["Spade", "Fork", "Hoe", "Rake", "Dibber"].map((n, i) => tool(i + 1, n)))]);
    expect(await screen.findByText("🔧 Bring: Spade, Fork, Hoe +2")).toBeInTheDocument();
  });

  it("still shows a visit with no bring list at all", async () => {
    setup([{ id: 1, title: "Old visit", notes: "", starts_at: "2026-11-07T09:00:00Z", duration_minutes: 60, task_ids: [] }]);
    expect(await screen.findByText("Old visit")).toBeInTheDocument();
    expect(screen.queryByText(/Bring:/)).not.toBeInTheDocument();
  });
});
