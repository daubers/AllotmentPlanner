import { combineLocalDateTime } from "./model";

describe("combineLocalDateTime", () => {
  it("combines a date and time into an ISO instant", () => {
    const iso = combineLocalDateTime("2026-11-07", "09:30");
    expect(iso).not.toBeNull();
    const d = new Date(iso!);
    expect(d.getFullYear()).toBe(2026);
    expect(d.getMonth()).toBe(10);
    expect(d.getDate()).toBe(7);
    expect(d.getHours()).toBe(9);
    expect(d.getMinutes()).toBe(30);
  });

  it("defaults a missing time to 9am", () => {
    const iso = combineLocalDateTime("2026-11-07", "");
    expect(new Date(iso!).getHours()).toBe(9);
  });

  it("returns null for an unparseable date", () => {
    expect(combineLocalDateTime("not-a-date", "09:00")).toBeNull();
  });
});
