import { describe, expect, it } from "vitest";
import { compass, dayOf, formatDuration, formatSize, groupByDay, mapLink, timeOf, type Media } from "./group";

const m = (id: number, taken_at: string, extra: Partial<Media> = {}): Media => ({ id, taken_at, ...extra }) as Media;

describe("groupByDay", () => {
  const items = [m(1, "2026-10-27T14:03:05+00:00"), m(2, "2026-10-27T09:00:00+00:00"), m(3, "2026-10-01T12:00:00+00:00")];

  it("groups by day, newest day first, keeping order within a day", () => {
    const days = groupByDay(items);
    expect(days.map((d) => d.date)).toEqual(["2026-10-27", "2026-10-01"]);
    expect(days[0].items.map((x) => x.id)).toEqual([1, 2]);
  });

  it("can order oldest first", () => {
    expect(groupByDay(items, false).map((d) => d.date)).toEqual(["2026-10-01", "2026-10-27"]);
  });

  it("uses the UTC date so late-evening photos stay on their day", () => {
    expect(dayOf(m(1, "2026-10-27T23:59:00+00:00"))).toBe("2026-10-27");
    expect(timeOf(m(1, "2026-10-27T23:59:00+00:00"))).toBe("23:59");
  });

  it("handles an empty list", () => {
    expect(groupByDay([])).toEqual([]);
  });
});

describe("formatting", () => {
  it("builds a map link only when there is a position", () => {
    expect(mapLink(m(1, "x", { lat: 51.5, lng: -0.12 }))).toContain("mlat=51.5&mlon=-0.12");
    expect(mapLink(m(1, "x", { lat: null, lng: null }))).toBeNull();
    expect(mapLink(m(1, "x", { lat: 0, lng: 0 }))).not.toBeNull(); // 0 is a valid coordinate
  });

  it("names compass directions, wrapping at north", () => {
    expect([0, 45, 90, 180, 270, 359, 360, -90].map(compass)).toEqual(["N", "NE", "E", "S", "W", "N", "N", "W"]);
    expect(compass(null)).toBeNull();
  });

  it("formats durations and sizes", () => {
    expect(formatDuration(65.4)).toBe("1:05");
    expect(formatDuration(null)).toBe("");
    expect(formatSize(500)).toBe("1 KB");
    expect(formatSize(1536 * 1024)).toBe("1.5 MB");
  });
});
