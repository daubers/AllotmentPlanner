import { existsSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { SCREENS, screenUrl } from "./screens";

describe("landing page screenshots", () => {
  it.each(Object.keys(SCREENS) as (keyof typeof SCREENS)[])("%s exists on disk and has alt text", (key) => {
    expect(existsSync(join(__dirname, "../../public", screenUrl(key)))).toBe(true);
    expect(SCREENS[key].alt.length).toBeGreaterThan(10);
  });
});
