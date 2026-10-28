import { existsSync } from "fs";
import { join } from "path";

// Expo Router uses src/app instead of app when it exists, which silently turns every file in it
// into a screen and hides the real routes. Keep shared code out of a folder called "app".
test("there is no src/app folder to hijack the routes", () => {
  expect(existsSync(join(__dirname, "app"))).toBe(false);
  expect(existsSync(join(__dirname, "..", "app", "_layout.tsx"))).toBe(true);
});
