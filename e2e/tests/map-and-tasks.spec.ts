import { expect, test, type Page } from "@playwright/test";

/** The menu is two rows: choose a group, then a page within it. */
async function openPage(page: Page, group: string, name: string) {
  await page.getByRole("navigation", { name: "Sections" }).getByRole("link", { name: group, exact: true }).click();
  await page.getByRole("navigation", { name: `${group} pages` }).getByRole("link", { name, exact: true }).click();
}

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

  // A visitor sees the landing page first, with the privacy and help pages one click away.
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Your allotment, on one map." })).toBeVisible();
  await page.goto("/privacy");
  await expect(page.getByRole("heading", { name: "Privacy", level: 1 })).toBeVisible();
  await page.goto("/help/map");
  await expect(page.getByRole("heading", { name: "The map", level: 1 })).toBeVisible();
  await page.goto("/");
  await page.getByRole("link", { name: "Sign in" }).first().click();
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

  // The Today sheet: undated jobs are hidden until asked for, then listed under their bed,
  // and the print stylesheet strips the app chrome. The PDF is kept for eyeballing.
  await openPage(page, "Work", "Today");
  await expect(page.getByText("Nothing due")).toBeVisible();
  await page.getByLabel("Include jobs with no date").click();
  const sheet = page.getByLabel("Todo list");
  await expect(sheet.getByRole("heading", { name: "Bed 1" })).toBeVisible();
  await expect(sheet.getByText("Water the beans")).toBeVisible();
  await expect(sheet.locator(".pin-n")).toHaveText("1");
  await page.emulateMedia({ media: "print" });
  await expect(page.locator(".subbar")).toBeHidden();
  await expect(page.locator(".today-controls")).toBeHidden();
  await page.pdf({ path: "test-results/today.pdf", format: "A4" });
  await page.setViewportSize({ width: 794, height: 700 }); // A4 width at 96dpi
  await page.screenshot({ path: "test-results/today-print.png" });
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.emulateMedia({ media: "screen" });

  // The Tasks page shows it with its location, and completing it moves it away.
  await openPage(page, "Work", "Tasks");
  await expect(page.getByText("Water the beans")).toBeVisible();
  await expect(page.getByText("📍 Bed 1")).toBeVisible();
  // A task made in the dialog can be edited afterwards.
  await page.getByRole("button", { name: "+ New task" }).click();
  await page.getByLabel("Title").fill("Buy string");
  await page.getByLabel("Notes").fill("Green, thin");
  await page.getByRole("button", { name: "Add task" }).click();
  await page.getByRole("button", { name: "Buy string" }).click();
  await page.getByLabel("Title").fill("Buy twine");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("button", { name: "Buy twine" })).toBeVisible();
  await page.getByRole("button", { name: "Buy twine" }).click();
  await page.getByRole("button", { name: "Delete", exact: true }).click();
  await page.getByRole("button", { name: "Yes, delete" }).click();
  await expect(page.getByText("Buy twine")).toHaveCount(0);

  await page.getByLabel("Complete Water the beans").click();
  await expect(page.getByText("Nothing to do")).toBeVisible();
  await page.getByRole("button", { name: /Show completed \(1\)/ }).click();
  await expect(page.getByLabel("Reopen Water the beans")).toBeChecked();

  // The pin is gone from the map once the task is done, and the bed survived a reload.
  await openPage(page, "Plot", "Map");
  await expect(page.locator(".task-pin")).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole("button", { name: "Bed 1" })).toBeVisible();

  // Photos: upload two EXIF-dated photos attached to Bed 1 (processed by the Celery worker),
  // check the timeline, the lightbox metadata, the feature filter and the before/after slider.
  await openPage(page, "Record", "Photos");
  await page.getByLabel("Attach new uploads to").selectOption({ label: "Bed 1" });
  await page.getByLabel("Choose photos or videos").setInputFiles([
    "fixtures/bed-day1.jpg",
    "fixtures/bed-day2.jpg",
    "fixtures/not-a-photo.jpg",
  ]);
  await expect(page.getByText("✕ not-a-photo.jpg")).toContainText("Unsupported file type");
  await expect(page.getByText("✓ bed-day1.jpg")).toBeVisible();
  await expect(page.getByText("✓ bed-day2.jpg")).toBeVisible();
  await expect(page.getByRole("heading", { name: /Tuesday 3 November 2026/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Tuesday 27 October 2026/ })).toBeVisible();
  const thumbs = page.locator(".tile img");
  await expect(thumbs).toHaveCount(2); // appear once the worker has made thumbnails
  await expect.poll(() => thumbs.first().evaluate((i: HTMLImageElement) => i.complete && i.naturalWidth)).toBeGreaterThan(0);

  await page.getByRole("button", { name: /Open bed-day1.jpg/ }).click();
  const box = page.locator("dialog.lightbox");
  await expect(box.getByText("51.50000, -0.12000")).toBeVisible(); // GPS read from the EXIF
  await expect(box.getByText("from the camera")).toBeVisible();
  await expect(box.getByText(/facing E/)).toBeVisible();
  await box.getByLabel("Caption").fill("Bare soil, before planting");
  await box.getByLabel("Caption").blur();
  await expect(page.getByRole("button", { name: /Open Bare soil, before planting/ })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(box).toHaveCount(0); // Escape closes (unmounts) the lightbox

  await page.getByLabel("Filter by feature").selectOption({ label: "Bed 1" });
  await expect(thumbs).toHaveCount(2);
  await page.getByRole("button", { name: "Compare over time" }).click();
  await expect(page.getByLabel("Before and after comparison")).toBeVisible();
  await page.getByLabel("Slide between before and after").fill("30");
  await page.screenshot({ path: "test-results/photos.png" });

  await openPage(page, "Record", "Overview");
  await expect(page.getByRole("heading", { name: /This week you .*added 2 photos/ })).toBeVisible();
  await expect(page.getByText(/1 day in a row/)).toBeVisible();
  await expect(page.locator(".heatmap .heat.l4")).toHaveCount(1); // today is the busiest (only) day
  await expect(page.locator(".tile img")).toHaveCount(2); // latest photos
  await page.screenshot({ path: "test-results/overview.png" });

  await openPage(page, "Plot", "Map from photos");
  await expect(page.getByRole("heading", { name: "From your photos" })).toBeVisible();
  await expect(page.getByText(/None built\./)).toBeVisible();
  // The two fixture photos are the same file, so the second counts as a repeat and is left out.
  await expect(page.getByText(/1 photo \(1 with a location\): about 1 image in all\./)).toBeVisible();
  await expect(page.getByText(/1 file looks like a second upload of another/)).toBeVisible();
  await expect(page.getByText(/Pick at least 5 photos/)).toBeVisible(); // not enough to build a map yet
  await expect(page.getByRole("button", { name: "Start" })).toBeDisabled();
  await page.screenshot({ path: "test-results/layers.png", fullPage: true });

  await page.getByRole("link", { name: "Settings" }).click();
  await expect(page.getByRole("heading", { name: "Mastodon" })).toBeVisible();
  await expect(page.getByText("Nothing posted yet.")).toBeVisible();
  await page.getByLabel("Instance").fill("https://127.0.0.1");
  await page.getByLabel("Access token").fill("not-a-real-token-123");
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page.getByRole("alert")).toContainText("private network"); // the SSRF guard, end to end
  await page.screenshot({ path: "test-results/settings.png" });

  // A video: uploaded like a photo, shown with its length, playable, and offered to the map builder.
  await openPage(page, "Record", "Photos");
  await page.getByLabel("Choose photos or videos").setInputFiles("fixtures/walk.mp4");
  await expect(page.getByText("✓ walk.mp4")).toBeVisible();
  await expect(page.locator(".tile-badge")).toContainText("0:03");
  await page.getByRole("button", { name: /Open walk.mp4/ }).click();
  const video = page.locator("dialog.lightbox video");
  await expect(video).toBeVisible();
  await expect.poll(() => video.evaluate((v: HTMLVideoElement) => v.readyState)).toBeGreaterThanOrEqual(1);
  await expect.poll(() => video.evaluate((v: HTMLVideoElement) => Math.round(v.duration))).toBe(3);
  await page.keyboard.press("Escape");
  await openPage(page, "Plot", "Map from photos");
  await expect(page.getByText(/1 photo \(1 with a location\), 1 video: about 4 images in all\./)).toBeVisible();
  await expect(page.getByText(/Videos are sampled about once a second/)).toBeVisible();

  expect(errors).toEqual([]);
});
