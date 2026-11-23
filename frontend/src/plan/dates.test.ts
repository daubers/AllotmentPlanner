import { describe, expect, it } from "vitest";
import { addDays, nextInWindow, todayISO, toDay } from "./dates";

describe("date maths", () => {
  it("adds days across months and years", () => {
    expect(addDays("2026-03-01", 14)).toBe("2026-03-15");
    expect(addDays("2026-12-25", 10)).toBe("2027-01-04");
    expect(addDays("2026-03-01", -1)).toBe("2026-02-28");
    expect(addDays("2028-02-28", 1)).toBe("2028-02-29");
  });

  it("counts whole days regardless of timezone", () => {
    expect(toDay("2026-03-29") - toDay("2026-03-28")).toBe(1); // a clock-change weekend
    expect(toDay("2026-10-25") - toDay("2026-10-24")).toBe(1);
  });

  it("formats today in local time", () => {
    expect(todayISO(new Date(2026, 0, 5, 23, 59))).toBe("2026-01-05");
  });
});

describe("nextInWindow", () => {
  it("stays put inside the window", () => expect(nextInWindow([3, 4, 5], "2026-04-17")).toBe("2026-04-17"));
  it("waits for the next month", () => expect(nextInWindow([3, 4, 5], "2026-01-20")).toBe("2026-03-01"));
  it("rolls into next year", () => {
    expect(nextInWindow([11, 12, 1, 2], "2026-08-10")).toBe("2026-11-01");
    expect(nextInWindow([2, 3], "2026-12-05")).toBe("2027-02-01");
  });
  it("is null with no months", () => {
    expect(nextInWindow([], "2026-01-01")).toBeNull();
    expect(nextInWindow(undefined, "2026-01-01")).toBeNull();
  });
});
