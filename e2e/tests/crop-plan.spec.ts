import { expect, test, type Page } from "@playwright/test";

/** The menu is two rows: choose a group, then a page within it. */
async function openPage(page: Page, group: string, name: string) {
  await page.getByRole("navigation", { name: "Sections" }).getByRole("link", { name: group, exact: true }).click();
  await page.getByRole("navigation", { name: `${group} pages` }).getByRole("link", { name, exact: true }).click();
}

const email = `e2e-plan-${Date.now()}@example.com`;
const DLAT = 1 / 111_320;
const DLON = 1 / (111_320 * Math.cos((51 * Math.PI) / 180));
/** A bed of `m` metres a side. */
const square = (m: number) => ({
  type: "Polygon",
  coordinates: [[[0, 0], [m, 0], [m, m], [0, m], [0, 0]].map(([x, y]) => [-1 + x * DLON, 51 + y * DLAT])],
});
const iso = (days: number) => new Date(Date.now() + days * 86_400_000).toISOString().slice(0, 10);

test("plan a bed with a succession, make its tasks, plant one crop", async ({ page, request }) => {
  page.on("pageerror", (e) => console.log(`[browser pageerror] ${e.message}`));

  // A signed-in user with a plot and a 100 m2 bed, set up through the API.
  const reg = await request.post("/api/v1/auth/register", { data: { email, display_name: "Planner", password: "password123" } });
  const tokens = await reg.json();
  const auth = { Authorization: `Bearer ${tokens.access_token}` };
  const plot = await (await request.post("/api/v1/allotments", { data: { name: "Plan plot" }, headers: auth })).json();
  const bed = await request.post(`/api/v1/allotments/${plot.id}/features`, {
    data: { type: "Feature", geometry: square(10), properties: { name: "Bed 1", kind: "bed" } },
    headers: auth,
  });
  expect(bed.status()).toBe(201);
  await page.addInitScript((t) => localStorage.setItem("allotment.tokens", t), JSON.stringify({ access_token: tokens.access_token, refresh_token: tokens.refresh_token }));

  await page.goto(`/allotments/${plot.id}`);
  await openPage(page, "Grow", "Plan");
  await expect(page.getByRole("heading", { name: "Plan", level: 1 })).toBeVisible();
  const section = page.getByRole("region", { name: "Bed 1" });
  await expect(section.getByText("about 100 m²")).toBeVisible();

  // Three lettuce sowings, a fortnight apart, each taking 2 m2 of the bed.
  await section.getByRole("button", { name: "Add crop" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.locator("select").first().selectOption({ label: "Lettuce" });
  await expect(dialog.getByLabel("Name on the plan")).toHaveValue("Lettuce");
  await dialog.getByLabel("Plants (optional)").fill("20");
  await expect(dialog.getByText(/About 1\.8 m² for 20 plants at 30 × 30 cm/)).toBeVisible();
  await dialog.getByRole("button", { name: "Use 1.8 m²" }).click();
  await dialog.getByLabel("Sow on").fill(iso(20));
  await dialog.getByLabel("Bed free again on").fill(iso(90));
  await dialog.getByLabel("Repeat as a succession").check();
  await dialog.getByLabel("Every (days)").fill("14");
  await dialog.getByLabel("Sowings in all").fill("3");
  await dialog.getByRole("button", { name: "Add succession" }).click();
  await expect(section.getByRole("button", { name: /^Edit Lettuce, 1\.8 m²/ })).toHaveCount(3);
  await expect(section.getByText("Overbooked")).toHaveCount(0); // 5.4 m2 of 100 m2

  // The jobs the plan implies become tasks: a sowing and a clearing for each.
  const plan = page.getByRole("region", { name: "Tasks from the plan" });
  await expect(plan.getByText("Sow Lettuce in Bed 1").first()).toBeVisible();
  await plan.getByRole("button", { name: "Add 6 tasks" }).click();
  await expect(plan.getByText("Added 6 tasks.")).toBeVisible();

  // A repeating job on the bed, made ahead as dated tasks.
  await plan.getByRole("button", { name: "Add a repeating job" }).click();
  const job = page.getByRole("dialog");
  await expect(job.getByLabel("Job")).toHaveValue("Weed Bed 1");
  await job.getByRole("button", { name: "Add job" }).click();
  await expect(job).toBeHidden();

  await openPage(page, "Work", "Tasks");
  await expect(page.getByText("Sow Lettuce in Bed 1").first()).toBeVisible();
  await expect(page.getByText("Weed Bed 1").first()).toBeVisible();

  // Sown for real: plant the first one, drawing its area, and the plan marks it done.
  await openPage(page, "Grow", "Plan");
  await section.getByRole("button", { name: /^Edit Lettuce, 1\.8 m²/ }).first().click();
  await page.getByRole("dialog").getByRole("link", { name: "Plant this in Bed 1" }).click();
  await expect(page.getByText(/Planting from your plan:/)).toBeVisible();
  await expect(page.getByLabel("Seeds or plants")).toHaveValue("20");
  await page.getByRole("button", { name: "Whole bed" }).click();
  await page.getByRole("button", { name: "Add planting" }).click();
  await expect(page.getByText(/Planting from your plan:/)).toBeHidden();

  await openPage(page, "Grow", "Plan");
  await section.getByRole("button", { name: /^Edit Lettuce, 1\.8 m²/ }).first().click();
  await expect(page.getByRole("dialog").getByRole("link", { name: "See it in Bed 1" })).toBeVisible();
});
