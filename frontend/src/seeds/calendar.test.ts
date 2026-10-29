import { describe, expect, it } from "vitest";
import { currentMonth, daysLabel, monthsLabel, toggleMonth } from "./calendar";

describe("toggleMonth", () => {
  it("adds in order and removes", () => {
    expect(toggleMonth([3, 9], 5)).toEqual([3, 5, 9]);
    expect(toggleMonth([3, 5, 9], 5)).toEqual([3, 9]);
    expect(toggleMonth(undefined, 2)).toEqual([2]);
  });
});

describe("monthsLabel", () => {
  it("joins runs", () => {
    expect(monthsLabel([3, 4, 5, 9])).toBe("Mar to May, Sep");
  });
  it("carries a run over the new year", () => {
    expect(monthsLabel([11, 12, 1, 2])).toBe("Nov to Feb");
  });
  it("handles single, empty and full", () => {
    expect(monthsLabel([6])).toBe("Jun");
    expect(monthsLabel([])).toBe("");
    expect(monthsLabel([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])).toBe("All year");
  });
});

describe("daysLabel", () => {
  it("describes ranges and singles", () => {
    expect(daysLabel(7, 14)).toBe("7 to 14 days");
    expect(daysLabel(10, 10)).toBe("10 days");
    expect(daysLabel(null, 21)).toBe("21 days");
    expect(daysLabel(null, null)).toBe("");
  });
});

describe("currentMonth", () => {
  it("is 1 to 12", () => {
    expect(currentMonth(new Date(2026, 0, 15))).toBe(1);
    expect(currentMonth(new Date(2026, 11, 15))).toBe(12);
  });
});
