import { describe, expect, it } from "vitest";
import { barStyle, currentKey, makeWindow, parseKey, peakUsage, shiftMonth } from "./window";

describe("the twelve month window", () => {
  it("shifts across year boundaries", () => {
    expect(shiftMonth("2026-11", 3)).toBe("2027-02");
    expect(shiftMonth("2026-01", -1)).toBe("2025-12");
    expect(shiftMonth("2026-06", 12)).toBe("2027-06");
    expect(shiftMonth("2026-06", 0)).toBe("2026-06");
  });

  it("covers twelve months from the first", () => {
    const w = makeWindow("2026-09");
    expect(w.months.map((m) => m.label)).toEqual(["Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug"]);
    expect(w.from).toBe("2026-09-01");
    expect(w.to).toBe("2027-08-31");
    expect(w.months[4]).toMatchObject({ key: "2027-01", year: 2027, start: "2027-01-01", end: "2027-02-01" });
  });

  it("reads a from= value, ignoring rubbish", () => {
    expect(parseKey("2026-04", "2026-01")).toBe("2026-04");
    for (const bad of [null, "", "2026-13", "2026-4", "April", "2026-04-01"]) expect(parseKey(bad, "2026-01")).toBe("2026-01");
    expect(currentKey(new Date(2026, 10, 23))).toBe("2026-11");
  });
});

describe("barStyle", () => {
  const w = makeWindow("2026-01"); // 365 days
  it("places a bar as a share of the window", () => {
    const b = barStyle("2026-01-01", "2026-07-02", w)!; // 182 days
    expect(b.left).toBe(0);
    expect(b.width).toBeCloseTo((182 / 365) * 100);
    expect(b.clippedLeft).toBe(false);
    expect(b.clippedRight).toBe(false);
  });

  it("clips bars that run past either edge, and says so", () => {
    const b = barStyle("2025-11-01", "2026-02-01", w)!;
    expect(b.left).toBe(0);
    expect(b.clippedLeft).toBe(true);
    expect(b.width).toBeCloseTo((31 / 365) * 100);
    const c = barStyle("2026-12-01", "2027-03-01", w)!;
    expect(c.clippedRight).toBe(true);
    expect(c.left + c.width).toBeCloseTo(100);
  });

  it("is null outside the window", () => {
    expect(barStyle("2025-01-01", "2025-12-31", w)).toBeNull();
    expect(barStyle("2027-01-01", "2027-02-01", w)).toBeNull();
    expect(barStyle("2025-12-01", "2026-01-01", w)).toBeNull(); // the end day itself is free
  });
});

describe("peakUsage", () => {
  const w = makeWindow("2026-03");
  it("is the most used on any day of each month", () => {
    const items = [
      { area_m2: 6, sow_on: "2026-03-01", end_on: "2026-05-01" },
      { area_m2: 4, sow_on: "2026-04-10", end_on: "2026-04-20" },
    ];
    const peaks = peakUsage(items, w);
    expect(peaks.slice(0, 4)).toEqual([6, 10, 0, 0]); // Mar, Apr, May, Jun
  });

  it("uses the plant-out date for a transplant and ignores skipped items", () => {
    const items = [
      { area_m2: 5, sow_on: "2026-03-01", plant_out_on: "2026-04-15", end_on: "2026-06-01" },
      { area_m2: 9, sow_on: "2026-03-01", end_on: "2026-06-01", status: "skipped" },
    ];
    expect(peakUsage(items, w).slice(0, 3)).toEqual([0, 5, 5]);
  });
});
