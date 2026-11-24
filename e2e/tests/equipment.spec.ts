import { expect, test, type Page } from "@playwright/test";

/** The menu is two rows: choose a group, then a page within it. */
async function openPage(page: Page, group: string, name: string) {
  await page.getByRole("navigation", { name: "Sections" }).getByRole("link", { name: group, exact: true }).click();
  await page.getByRole("navigation", { name: `${group} pages` }).getByRole("link", { name, exact: true }).click();
}

const email = `e2e-equip-${Date.now()}@example.com`;
const DLAT = 1 / 111_320;
const DLON = 1 / (111_320 * Math.cos((51 * Math.PI) / 180));
const square = (m: number) => ({
  type: "Polygon",
  coordinates: [[[0, 0], [m, 0], [m, m], [0, m], [0, 0]].map(([x, y]) => [-1 + x * DLON, 51 + y * DLAT])],
});
const iso = (days: number) => new Date(Date.now() + days * 86_400_000).toISOString().slice(0, 10);

test("equipment: suggested for a job, brought on a visit, maintained and put to use", async ({ page, request }) => {
  page.on("pageerror", (e) => console.log(`[browser pageerror] ${e.message}`));

  // A signed-in user with a plot, a bed and some kit, set up through the API.
  const reg = await request.post("/api/v1/auth/register", { data: { email, display_name: "Gardener", password: "password123" } });
  const tokens = await reg.json();
  const auth = { Authorization: `Bearer ${tokens.access_token}` };
  const plot = await (await request.post("/api/v1/allotments", { data: { name: "Kit plot" }, headers: auth })).json();
  const base = `/api/v1/allotments/${plot.id}`;
  await request.post(`${base}/features`, { data: { type: "Feature", geometry: square(10), properties: { name: "Bed 1", kind: "bed" } }, headers: auth });
  for (const body of [
    { name: "Border spade", kind: "spade" },
    { name: "Steel dibber", kind: "dibber" },
    { name: "Glass cloches", kind: "cloche", quantity: 6 },
  ]) expect((await request.post(`${base}/equipment`, { data: body, headers: auth })).status()).toBe(201);
  await page.addInitScript((t) => localStorage.setItem("allotment.tokens", t), JSON.stringify({ access_token: tokens.access_token, refresh_token: tokens.refresh_token }));

  // The inventory.
  await page.goto(`/allotments/${plot.id}`);
  await openPage(page, "Grow", "Equipment");
  await expect(page.getByRole("link", { name: /Border spade/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /Glass cloches/ })).toContainText("× 6");

  // A job that needs digging is offered the spade (and only what you own).
  await openPage(page, "Work", "Tasks");
  await page.getByRole("button", { name: "+ New task" }).click();
  const task = page.getByRole("dialog");
  await task.getByLabel("Title").fill("Dig over the bed");
  const suggested = task.getByRole("button", { name: "Add Border spade" });
  await expect(suggested).toBeVisible({ timeout: 5000 });
  await expect(task.getByRole("button", { name: "Add Steel dibber" })).toHaveCount(0);
  await suggested.click();
  await task.getByLabel("Due date").fill(iso(1));
  await task.getByRole("button", { name: "Add task" }).click();
  await expect(page.getByText("🔧 Border spade")).toBeVisible();

  // A visit with that job brings the spade, and says so in the calendar entry.
  await openPage(page, "Work", "Visits");
  await page.getByRole("button", { name: "Plan a visit" }).click();
  const visit = page.getByRole("dialog");
  await visit.getByLabel("Title").fill("Saturday dig");
  await visit.getByRole("checkbox", { name: "Dig over the bed" }).check();
  await expect(visit.getByRole("button", { name: "Remove Border spade" })).toBeVisible();
  await visit.getByLabel("Add equipment").selectOption({ label: "Glass cloches" });
  await visit.getByRole("button", { name: "Plan visit" }).click();
  await expect(page.getByText("🔧 Bring: Border spade, Glass cloches")).toBeVisible();
  const visits = await (await request.get(`${base}/visits`, { headers: auth })).json();
  const ics = await (await request.get(`${base}/visits/${visits[0].id}/calendar.ics`, { headers: auth })).text();
  expect(ics.replace(/\r?\n /g, "")).toContain("Bring: Border spade\\, Glass cloches");

  // Routine maintenance becomes dated jobs about the item.
  await openPage(page, "Grow", "Equipment");
  await page.getByRole("link", { name: /Border spade/ }).click();
  const maintenance = page.getByRole("region", { name: "Maintenance" });
  await maintenance.getByLabel("Job").fill("Sharpen");
  await maintenance.getByRole("button", { name: "Schedule maintenance" }).click();
  await expect(maintenance.getByText("Sharpen Border spade")).toBeVisible();
  await expect(maintenance.getByText(/Next due/)).toBeVisible();

  // Cloches put to use on a bed: more than you own is flagged, not refused.
  await openPage(page, "Grow", "Equipment");
  await page.getByRole("link", { name: /Glass cloches/ }).click();
  for (const how of ["4", "3"]) {
    await page.getByRole("button", { name: "Put equipment to use" }).click();
    const use = page.getByRole("dialog");
    await use.getByLabel("Bed").selectOption({ label: "Bed 1" });
    await use.getByLabel("How many").fill(how);
    await use.getByRole("button", { name: "Put to use" }).click();
    await expect(use).toBeHidden();
  }
  await expect(page.getByText(/You have 6 but 7 are in use/)).toBeVisible();
});
