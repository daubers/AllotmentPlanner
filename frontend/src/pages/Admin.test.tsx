import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
vi.mock("../api/client", () => ({
  api: { GET: (...a: unknown[]) => get(...a), POST: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() },
  authHeader: async () => null,
  sessionRejected: vi.fn(),
}));
let isAdmin = true;
vi.mock("../auth", () => ({ useAuth: () => ({ user: { id: 1, display_name: "Ann", is_admin: isAdmin } }) }));

import AdminPage from "./AdminPage";

const WORKERS = {
  workers: [
    {
      name: "celery@gpu", queues: ["mapping", "vision"], concurrency: 1, pid: 7, uptime_seconds: 3700, processed: 12, reserved: 1,
      active: [{ id: "t1", name: "allotment.run_map_job", running_seconds: 125 }], version: "0.8.1", gpu: "AMD Radeon RX 6600",
    },
  ],
  queues: [{ name: "celery", depth: 0, consumers: 0 }, { name: "mapping", depth: 2, consumers: 1 }, { name: "vision", depth: 3, consumers: 0 }],
  beat: [{ name: "mastodon-sweep", task: "allotment.mastodon_sweep", schedule: "every 5 min", last_run: null, last_state: null }],
  error: null,
  checked_at: "2026-11-01T12:00:00Z",
};
const SYSTEM = {
  version: "0.8.1", server_time: "2026-11-01T12:00:00Z", checks: { database: "ok", redis: "error: ConnectionError", storage: "ok" },
  users: 3, allotments: 2, log_rows: 40, log_retention_days: 14,
};
const JOBS = {
  jobs: [
    { kind: "map", id: 4, label: "Whole plot", status: "failed", stage: null, error: "out of memory", allotment_id: 1, allotment_name: "Plot", created_at: "2026-11-01T10:00:00Z", started_at: "2026-11-01T10:00:00Z", finished_at: "2026-11-01T10:10:00Z" },
  ],
  counts: [{ kind: "map", waiting: 0, failed_24h: 1 }],
};
const entry = (id: number, extra: Record<string, unknown>) => ({
  id, at: "2026-11-01T11:00:00Z", service: "worker", host: "gpu", level: "error", event: `line ${id}`, request_id: null, task_id: null, data: null, ...extra,
});

function setup(url = "/admin") {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[url]}>
        <AdminPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  isAdmin = true;
  get.mockReset();
  get.mockImplementation(async (p: string, opts?: { params?: { query?: Record<string, unknown> } }) => {
    if (p.endsWith("/workers")) return { data: WORKERS };
    if (p.endsWith("/system")) return { data: SYSTEM };
    if (p.endsWith("/jobs")) return { data: JOBS };
    if (p.endsWith("/logs")) {
      const q = opts?.params?.query ?? {};
      if (q.before_id) return { data: { entries: [entry(1, { event: "older line" })], next_before: null, services: ["worker"] } };
      return {
        data: { entries: [entry(3, { event: "Task blew up\nTraceback…", task_id: "abcdef123456" }), entry(2, { level: "warning" })], next_before: 2, services: ["api", "worker"] },
      };
    }
    return { data: {} };
  });
});

describe("Admin page", () => {
  it("is for admins only", () => {
    isAdmin = false;
    setup();
    expect(screen.getByText(/for site admins/)).toBeInTheDocument();
    expect(get).not.toHaveBeenCalled();
  });

  it("shows each worker, what it is running and its GPU", async () => {
    setup();
    const card = (await screen.findByText("celery@gpu")).closest("li")!;
    expect(within(card).getByText(/GPU: AMD Radeon RX 6600/)).toBeInTheDocument();
    expect(within(card).getByText(/v0.8.1/)).toBeInTheDocument();
    expect(within(card).getByText("allotment.run_map_job")).toBeInTheDocument();
    expect(within(card).getByText(/for 2 min/)).toBeInTheDocument();
  });

  it("flags a queue nobody is listening to and a failing dependency", async () => {
    setup();
    expect(await screen.findByText(/nothing is picking these up/)).toBeInTheDocument();
    expect(screen.getByText("error: ConnectionError")).toBeInTheDocument();
    expect(screen.getAllByText("OK")).toHaveLength(2);
  });

  it("says so when no worker answers", async () => {
    get.mockImplementation(async (p: string) => ({ data: p.endsWith("/workers") ? { ...WORKERS, workers: [] } : SYSTEM }));
    setup();
    expect(await screen.findByText(/No worker answered/)).toBeInTheDocument();
  });

  it("lists recent jobs with their errors", async () => {
    setup("/admin?tab=jobs");
    expect(await screen.findByText("Whole plot")).toBeInTheDocument();
    expect(screen.getByText("out of memory")).toBeInTheDocument();
    expect(screen.getByText("1 failed today")).toBeInTheDocument();
  });

  it("shows warnings and errors first, and pages back through older lines", async () => {
    setup("/admin?tab=logs");
    expect(await screen.findByText("Task blew up")).toBeInTheDocument();
    expect(get).toHaveBeenCalledWith("/api/v1/admin/logs", expect.objectContaining({ params: { query: expect.objectContaining({ level: "warning" }) } }));
    await userEvent.click(screen.getByRole("button", { name: "Load older" }));
    expect(await screen.findByText("older line")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Load older" })).not.toBeInTheDocument();
  });

  it("filters to one task when its link is clicked", async () => {
    setup("/admin?tab=logs");
    await screen.findByText("Task blew up");
    await userEvent.click(screen.getByRole("button", { name: "task" }));
    await waitFor(() =>
      expect(get).toHaveBeenCalledWith("/api/v1/admin/logs", expect.objectContaining({ params: { query: expect.objectContaining({ task_id: "abcdef123456" }) } })),
    );
    expect(screen.getByRole("button", { name: /task abcdef12/ })).toBeInTheDocument();
  });

  it("searches the messages", async () => {
    setup("/admin?tab=logs");
    await screen.findByText("Task blew up");
    await userEvent.type(screen.getByLabelText("Search"), "boom");
    await waitFor(() =>
      expect(get).toHaveBeenLastCalledWith("/api/v1/admin/logs", expect.objectContaining({ params: { query: expect.objectContaining({ q: "boom" }) } })),
    );
  });
});
