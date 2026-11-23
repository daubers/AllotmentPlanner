import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
const post = vi.fn();
const patch = vi.fn();
const del = vi.fn();
vi.mock("../api/client", () => ({
  api: { GET: (...a: unknown[]) => get(...a), POST: (...a: unknown[]) => post(...a), PATCH: (...a: unknown[]) => patch(...a), DELETE: (...a: unknown[]) => del(...a) },
  authHeader: async () => null,
  sessionRejected: vi.fn(),
}));

import EquipmentItemPage from "./EquipmentItemPage";
import EquipmentPage from "./EquipmentPage";

const kinds = [
  { key: "spade", label: "Spade" },
  { key: "dibber", label: "Dibber" },
  { key: "cloche", label: "Cloche" },
];
const item = (extra = {}) => ({
  id: 4, name: "Border spade", kind: "spade", kind_label: "Spade", quantity: 1, notes: "Ash handle", used_for: "dig, trench", keywords: ["dig", "trench"],
  status: "in_service", location_feature_id: 9, location_name: "Shed", last_serviced_on: null, created_at: "2026-11-01T10:00:00Z", updated_at: "2026-11-01T10:00:00Z", ...extra,
});
const cloches = item({ id: 5, name: "Glass cloches", kind: "cloche", kind_label: "Cloche", quantity: 6, location_name: null, location_feature_id: null });
const old = item({ id: 6, name: "Old fork", kind: null, kind_label: "Other", status: "out_of_action", location_name: null });

let maintenance: Record<string, unknown> = { schedules: [], next_due: null, overdue: false, open_tasks: 0, last_serviced_on: null };

function setup(url: string, role: "owner" | "viewer" = "owner") {
  const context = { id: 1, allotment: { id: 1, name: "Plot", role }, canEdit: role !== "viewer" };
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/a" element={<Outlet context={context} />}>
            <Route path="equipment" element={<EquipmentPage />} />
            <Route path="equipment/:equipmentId" element={<EquipmentItemPage />} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  for (const m of [get, post, patch, del]) m.mockReset();
  maintenance = { schedules: [], next_due: null, overdue: false, open_tasks: 0, last_serviced_on: null };
  get.mockImplementation(async (p: string) => {
    if (p.endsWith("/equipment-kinds")) return { data: kinds };
    if (p.endsWith("/equipment/{equipment_id}/maintenance")) return { data: maintenance };
    if (p.endsWith("/equipment/{equipment_id}")) return { data: item() };
    if (p.endsWith("/equipment")) return { data: [item(), cloches, old] };
    if (p.endsWith("/features")) return { data: { features: [{ id: 9, geometry: {}, properties: { name: "Shed", kind: "shed" } }] } };
    return { data: [] };
  });
  post.mockResolvedValue({ data: item({ id: 11 }) });
  patch.mockResolvedValue({ data: item() });
  del.mockResolvedValue({});
});

describe("Equipment list", () => {
  it("shows what you own, how many, where, and what is out of action", async () => {
    setup("/a/equipment");
    const spade = await screen.findByRole("link", { name: /Border spade/ });
    expect(spade).toHaveTextContent("Spade · Shed");
    expect(spade).toHaveAttribute("href", "/a/equipment/4");
    expect(screen.getByRole("link", { name: /Glass cloches/ })).toHaveTextContent("× 6");
    expect(screen.getByRole("link", { name: /Old fork/ })).toHaveTextContent("Out of action");
    expect(within(screen.getByRole("link", { name: /Border spade/ })).queryByText(/×/)).not.toBeInTheDocument(); // one of something has no count
  });

  it("asks for what the filters say", async () => {
    setup("/a/equipment");
    await screen.findByRole("link", { name: /Border spade/ });
    await userEvent.selectOptions(screen.getByLabelText("Kind filter"), "cloche");
    await userEvent.selectOptions(screen.getByLabelText("Status filter"), "out_of_action");
    await userEvent.type(screen.getByLabelText("Search equipment"), "fork");
    await waitFor(() =>
      expect(get).toHaveBeenCalledWith(
        expect.stringMatching(/\/equipment$/),
        expect.objectContaining({ params: expect.objectContaining({ query: { q: "fork", kind: "cloche", status: "out_of_action" } }) }),
      ),
    );
  });

  it("says so when nothing matches, and when there is nothing yet", async () => {
    get.mockImplementation(async (p: string) => ({ data: p.endsWith("/equipment-kinds") ? kinds : [] }));
    setup("/a/equipment");
    expect(await screen.findByText("Nothing here yet. Add the first item above.")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Search equipment"), "zzz");
    expect(await screen.findByText("Nothing matches.")).toBeInTheDocument();
  });

  it("adds an item and opens it", async () => {
    setup("/a/equipment");
    await screen.findAllByRole("option", { name: "Dibber" });
    await userEvent.type(screen.getByLabelText("Name"), "Steel dibber");
    await userEvent.selectOptions(screen.getByLabelText("Kind"), "dibber");
    const many = screen.getByLabelText("How many");
    await userEvent.clear(many);
    await userEvent.type(many, "2");
    await userEvent.click(screen.getByRole("button", { name: "Add equipment" }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][1].body).toEqual({ name: "Steel dibber", kind: "dibber", quantity: 2 });
    expect(await screen.findByRole("heading", { name: "Border spade" })).toBeInTheDocument(); // the new item's page
  });

  it("shows a refusal", async () => {
    post.mockResolvedValue({ error: { message: "Name is too long" } });
    setup("/a/equipment");
    await userEvent.type(await screen.findByLabelText("Name"), "x");
    await userEvent.click(screen.getByRole("button", { name: "Add equipment" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Name is too long");
  });

  it("is look-only for a viewer", async () => {
    setup("/a/equipment", "viewer");
    await screen.findByRole("link", { name: /Border spade/ });
    expect(screen.queryByRole("button", { name: "Add equipment" })).not.toBeInTheDocument();
  });
});

describe("Equipment item", () => {
  it("shows the item and saves changes", async () => {
    setup("/a/equipment/4");
    expect(await screen.findByRole("heading", { name: "Border spade" })).toBeInTheDocument();
    expect(await screen.findByLabelText("Kind")).toHaveValue("spade");
    expect(screen.getByLabelText("Kept in")).toHaveValue("9");
    expect(screen.getByLabelText(/Used for/)).toHaveValue("dig, trench");
    const many = screen.getByLabelText("How many");
    await userEvent.clear(many);
    await userEvent.type(many, "3");
    await userEvent.selectOptions(screen.getByLabelText("Status"), "out_of_action");
    await userEvent.clear(screen.getByLabelText(/Used for/));
    await userEvent.type(screen.getByLabelText(/Used for/), "dig, turning compost");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(patch).toHaveBeenCalled());
    expect(patch.mock.calls[0][1]).toMatchObject({
      params: { path: { allotment_id: 1, equipment_id: 4 } },
      body: { name: "Border spade", kind: "spade", quantity: 3, status: "out_of_action", location_feature_id: 9, used_for: "dig, turning compost" },
    });
    expect(await screen.findByRole("status")).toHaveTextContent("Saved");
  });

  it("can clear its kind and place", async () => {
    setup("/a/equipment/4");
    await userEvent.selectOptions(await screen.findByLabelText("Kind"), "Other");
    await userEvent.selectOptions(screen.getByLabelText("Kept in"), "Nowhere in particular");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(patch).toHaveBeenCalled());
    expect(patch.mock.calls[0][1].body).toMatchObject({ kind: null, location_feature_id: null });
  });

  it("asks before deleting, then goes back to the list", async () => {
    setup("/a/equipment/4");
    await userEvent.click(await screen.findByRole("button", { name: "Delete" }));
    expect(del).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Really delete this?" }));
    await waitFor(() => expect(del).toHaveBeenCalled());
    expect(del.mock.calls[0][1]).toMatchObject({ params: { path: { allotment_id: 1, equipment_id: 4 } } });
    expect(await screen.findByRole("heading", { name: "Equipment" })).toBeInTheDocument();
  });

  it("shows a refusal and a missing item", async () => {
    patch.mockResolvedValue({ error: { message: "location_feature_id does not belong to this allotment" } });
    setup("/a/equipment/4");
    await userEvent.click(await screen.findByRole("button", { name: "Save" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("does not belong to this allotment");
  });

  it("says when the item is not there", async () => {
    get.mockImplementation(async () => ({ data: undefined }));
    setup("/a/equipment/4");
    expect(await screen.findByText(/Equipment not found/)).toBeInTheDocument();
  });

  it("is read-only for a viewer", async () => {
    setup("/a/equipment/4", "viewer");
    expect(await screen.findByRole("heading", { name: "Border spade" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Name")).toBeDisabled();
  });
});

describe("Maintenance", () => {
  const schedule = { id: 3, title: "Sharpen Border spade", rule: "every 3 months", until_on: "2027-11-01", open_tasks: 4, done_tasks: 1, equipment_id: 4 };
  const section = () => within(screen.getByRole("region", { name: "Maintenance" }));

  it("says when it was last serviced and when it is next due", async () => {
    maintenance = { schedules: [schedule], next_due: "2026-12-01", overdue: false, open_tasks: 4, last_serviced_on: "2026-03-12" };
    setup("/a/equipment/4");
    expect(await screen.findByText(/Last serviced 12 Mar 2026\./)).toBeInTheDocument();
    expect(screen.getByText(/Next due 1 Dec 2026\./)).toBeInTheDocument();
    expect(section().queryByText("Overdue")).not.toBeInTheDocument();
    expect(section().getByText("Sharpen Border spade")).toBeInTheDocument();
    expect(section().getByText(/every 3 months, until 1 Nov 2027\. 4 to do, 1 done\./)).toBeInTheDocument();
  });

  it("flags overdue maintenance, and says when nothing is planned", async () => {
    maintenance = { schedules: [], next_due: "2026-10-01", overdue: true, open_tasks: 1, last_serviced_on: null };
    setup("/a/equipment/4");
    expect(await screen.findByText(/No service recorded yet\./)).toBeInTheDocument();
    expect(await section().findByText("Overdue")).toBeInTheDocument(); // once the maintenance has loaded
  });

  it("says nothing is scheduled", async () => {
    setup("/a/equipment/4");
    expect(await screen.findByText(/Nothing scheduled\./)).toBeInTheDocument();
  });

  it("schedules a repeating job", async () => {
    post.mockResolvedValue({ data: schedule });
    setup("/a/equipment/4");
    await screen.findByRole("heading", { name: "Maintenance" });
    await userEvent.type(section().getByLabelText("Job"), "Sharpen");
    await userEvent.click(section().getByRole("button", { name: "Schedule maintenance" }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][0]).toMatch(/\/equipment\/\{equipment_id\}\/maintenance$/);
    expect(post.mock.calls[0][1].params.path).toEqual({ allotment_id: 1, equipment_id: 4 });
    const body = post.mock.calls[0][1].body;
    expect(body).toMatchObject({ title: "Sharpen Border spade", every_n: 3, unit: "month" });
    expect(body.until_on > body.starts_on).toBe(true);
  });

  it("can be a single job, which ends the day it starts", async () => {
    post.mockResolvedValue({ data: schedule });
    setup("/a/equipment/4");
    await screen.findByRole("heading", { name: "Maintenance" });
    await userEvent.click(section().getByLabelText("Just once"));
    expect(section().queryByLabelText("Until")).not.toBeInTheDocument();
    expect(section().queryByLabelText("Every")).not.toBeInTheDocument();
    await userEvent.click(section().getByRole("button", { name: "Schedule maintenance" }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    const body = post.mock.calls[0][1].body;
    expect(body.until_on).toBe(body.starts_on);
    expect(body.title).toBe(""); // the server names it "Service <item>"
  });

  it("shows a refusal", async () => {
    post.mockResolvedValue({ error: { message: "A series can have at most 366 occurrences" } });
    setup("/a/equipment/4");
    await screen.findByRole("heading", { name: "Maintenance" });
    await userEvent.click(section().getByRole("button", { name: "Schedule maintenance" }));
    expect(await section().findByRole("alert")).toHaveTextContent("at most 366");
  });

  it("asks before stopping a schedule", async () => {
    maintenance = { schedules: [schedule], next_due: "2026-12-01", overdue: false, open_tasks: 4, last_serviced_on: null };
    setup("/a/equipment/4");
    await screen.findByText("Sharpen Border spade");
    await userEvent.click(section().getByRole("button", { name: "Stop" }));
    expect(del).not.toHaveBeenCalled();
    await userEvent.click(section().getByRole("button", { name: "No" }));
    await userEvent.click(section().getByRole("button", { name: "Stop" }));
    await userEvent.click(section().getByRole("button", { name: "Yes, stop it" }));
    await waitFor(() => expect(del).toHaveBeenCalled());
    expect(del.mock.calls[0][1]).toMatchObject({ params: { path: { allotment_id: 1, series_id: 3 } } });
  });

  it("is look-only for a viewer", async () => {
    maintenance = { schedules: [schedule], next_due: "2026-12-01", overdue: false, open_tasks: 4, last_serviced_on: null };
    setup("/a/equipment/4", "viewer");
    expect(await screen.findByText("Sharpen Border spade")).toBeInTheDocument();
    expect(section().queryByRole("button", { name: "Stop" })).not.toBeInTheDocument();
    expect(section().queryByRole("button", { name: "Schedule maintenance" })).not.toBeInTheDocument();
  });

  it("saves a service date by hand, and clears it", async () => {
    get.mockImplementation(async (p: string) => {
      if (p.endsWith("/equipment/{equipment_id}/maintenance")) return { data: maintenance };
      if (p.endsWith("/equipment/{equipment_id}")) return { data: item({ last_serviced_on: "2026-03-12" }) };
      return { data: p.endsWith("/equipment-kinds") ? kinds : [] };
    });
    setup("/a/equipment/4");
    const field = await screen.findByLabelText(/Last serviced/);
    expect(field).toHaveValue("2026-03-12");
    await userEvent.clear(field);
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(patch).toHaveBeenCalled());
    expect(patch.mock.calls[0][1].body.last_serviced_on).toBeNull();
  });

  it("warns that deleting also removes upcoming maintenance", async () => {
    get.mockImplementation(async (p: string) => {
      if (p.endsWith("/equipment/{equipment_id}/maintenance")) return { data: maintenance };
      if (p.endsWith("/equipment/{equipment_id}")) return { data: item({ maintenance_tasks: 3 }) };
      return { data: p.endsWith("/equipment-kinds") ? kinds : [] };
    });
    setup("/a/equipment/4");
    await userEvent.click(await screen.findByRole("button", { name: "Delete" }));
    expect(screen.getByText(/This also removes 3 upcoming maintenance jobs\./)).toBeInTheDocument();
  });

  it("marks overdue equipment in the list", async () => {
    get.mockImplementation(async (p: string) => {
      if (p.endsWith("/equipment-kinds")) return { data: kinds };
      if (p.endsWith("/equipment")) return { data: [item({ overdue: true, next_due: "2026-10-01" }), cloches] };
      return { data: [] };
    });
    setup("/a/equipment");
    expect(await screen.findByRole("link", { name: /Border spade/ })).toHaveTextContent("Overdue");
    expect(screen.getByRole("link", { name: /Glass cloches/ })).not.toHaveTextContent("Overdue");
  });
});
