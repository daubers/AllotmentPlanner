import { describe, expect, it } from "vitest";
import { areaFromPercent, cellM2, hint, percentOfBed, suggestArea, suggestCount } from "./area";

const lettuce = { plant: 30, row: 30 };

describe("space a crop needs", () => {
  it("is plant spacing times row spacing", () => {
    expect(cellM2(lettuce)).toBeCloseTo(0.09);
    expect(cellM2({ plant: 5, row: 25 })).toBeCloseTo(0.0125);
    expect(cellM2({ plant: 30, row: null })).toBeCloseTo(0.09); // no row spacing: a square
  });

  it("is unknown without a plant spacing", () => {
    expect(cellM2({ plant: null, row: 25 })).toBeNull();
    expect(cellM2({ plant: 0, row: 25 })).toBeNull();
  });

  it("suggests an area rounded up to a tenth", () => {
    expect(suggestArea(20, lettuce)).toBe(1.8);
    expect(suggestArea(25, lettuce)).toBe(2.3); // 2.25 rounds up
    expect(suggestArea(1, { plant: 3, row: 3 })).toBe(0.1); // never zero
    expect(suggestArea(0, lettuce)).toBeNull();
    expect(suggestArea(10, { plant: null, row: null })).toBeNull();
  });

  it("suggests how many fit", () => {
    expect(suggestCount(1.8, lettuce)).toBe(20);
    expect(suggestCount(1, lettuce)).toBe(11);
    expect(suggestCount(0, lettuce)).toBeNull();
  });

  it("converts between percent and area", () => {
    expect(areaFromPercent(25, 8)).toBe(2);
    expect(percentOfBed(2, 8)).toBe(25);
    expect(areaFromPercent(33.3, 10)).toBe(3.3);
  });

  it("explains the suggestion", () => {
    expect(hint(20, lettuce)).toBe("About 1.8 m² for 20 plants at 30 × 30 cm");
    expect(hint(null, lettuce)).toContain("Each plant needs about 0.09 m²");
    expect(hint(20, { plant: null, row: null })).toBeNull();
  });
});
