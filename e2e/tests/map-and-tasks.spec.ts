import { expect, test, type Page } from "@playwright/test";

const email = `e2e-${Date.now()}@example.com`;

async function drawBed(page: Page) {
  const map = page.locator(".leaflet-container");
  const box = (await map.boundingBox())!;
  const cx = box.x + box.width / 2;
  const cy = box.y + box.height / 2;
  await page.locator(".leaflet-pm-icon-polygon").click();
  const pts: [number, number][] = [[-80, -60], [80, -60], [80, 60], [-80, 60]];
  for (const [dx, dy] of pts) await page.mouse.click(cx + dx, cy + dy);
  await page.mouse.click(cx + pts[0][0], cy + pts[0][1]); // click the first vertex to close
}

test("register, draw a bed, pin a task to it, complete it", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => m.type() === "error" && console.log(`[browser console] ${m.text()}`));
  page.on("pageerror", (e) => console.log(`[browser pageerror] ${e.message}`));

  await page.goto("/");
  await expect(page).toHaveURL(/\/login$/);
  await page.getByRole("button", { name: /Need an account/ }).click();
  await page.getByLabel("Your name").fill("E2E Gardener");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: "Register" }).click();

  await expect(page.getByRole("heading", { name: "Your allotments" })).toBeVisible();
  await page.getByLabel("New allotment name").fill("E2E plot");
  await page.getByRole("button", { name: "Create" }).click();
  await page.getByRole("link", { name: /E2E plot/ }).click();

  // Draw a polygon with the Geoman toolbar; the editor saves it to the API.
  await expect(page.locator(".leaflet-container")).toBeVisible();
  const created = page.waitForResponse((r) => r.url().endsWith("/features") && r.request().method() === "POST");
  await drawBed(page);
  expect((await created).status()).toBe(201);
  await expect(page.getByRole("button", { name: "Unnamed other" })).toBeVisible();

  // Name it and set its kind.
  await page.getByLabel("Name", { exact: true }).fill("Bed 1");
  await page.getByLabel("Name", { exact: true }).press("Enter"); // Enter saves (as does leaving the field)
  await page.getByLabel("Kind").selectOption("bed");
  await expect(page.getByRole("button", { name: "Bed 1" })).toBeVisible();

  // Quick-add a task pinned to the selected feature; a pin appears on the map.
  await page.getByLabel("New task for this feature").fill("Water the beans");
  await page.getByRole("button", { name: "Add", exact: true }).click();
  await expect(page.getByText("Water the beans")).toBeVisible();
  await expect(page.locator(".task-pin")).toHaveCount(1);

  // The Tasks page shows it with its location, and completing it moves it away.
  await page.getByRole("link", { name: "Tasks" }).click();
  await expect(page.getByText("Water the beans")).toBeVisible();
  await expect(page.getByText("📍 Bed 1")).toBeVisible();
  await page.getByLabel("Complete Water the beans").click();
  await expect(page.getByText("Nothing to do")).toBeVisible();
  await page.getByRole("button", { name: /Show completed \(1\)/ }).click();
  await expect(page.getByLabel("Reopen Water the beans")).toBeChecked();

  // The pin is gone from the map once the task is done, and the bed survived a reload.
  await page.getByRole("link", { name: "Map" }).click();
  await expect(page.locator(".task-pin")).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole("button", { name: "Bed 1" })).toBeVisible();

  expect(errors).toEqual([]);
});
