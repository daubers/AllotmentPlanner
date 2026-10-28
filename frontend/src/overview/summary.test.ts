import { describe, expect, it } from "vitest";
import { dayLabel, level, streakText, weekColumns, weekHeadline, type OverviewDay } from "./summary";

const day = (date: string, extra: Partial<OverviewDay> = {}): OverviewDay =>
  ({ date, tasks_done: 0, tasks_added: 0, photos_added: 0, map_edits: 0, total: 0, ...extra }) as OverviewDay;
const counts = (extra = {}) => ({ tasks_done: 0, tasks_added: 0, photos_added: 0, map_edits: 0, active_days: 0, ...extra });

describe("level", () => {
  it("is 0 when nothing happened and scales to 4 at the busiest day", () => {
    expect(level(0, 10)).toBe(0);
    expect(level(1, 10)).toBe(1);
    expect(level(5, 10)).toBe(2);
    expect(level(10, 10)).toBe(4);
  });
  it("handles an all-quiet window", () => expect(level(0, 0)).toBe(0));
});

describe("weekColumns", () => {
  it("pads the first week so Monday is row 0", () => {
    // Wed 10 Jun 2026 .. Mon 15 Jun 2026
    const cols = weekColumns(["10", "11", "12", "13", "14", "15"].map((d) => day(`2026-06-${d}`)));
    expect(cols).toHaveLength(2);
    expect(cols[0].slice(0, 2)).toEqual([null, null]);
    expect(cols[0][2]?.date).toBe("2026-06-10");
    expect(cols[1][0]?.date).toBe("2026-06-15");
    expect(cols[1].slice(1).every((c) => c === null)).toBe(true);
  });
  it("is empty for no data", () => expect(weekColumns([])).toEqual([]));
});

describe("weekHeadline", () => {
  it("encourages a quiet week", () => expect(weekHeadline(counts(), counts())).toMatch(/fresh week/));
  it("lists what happened and the improvement on last week", () => {
    const text = weekHeadline(counts({ tasks_done: 5, photos_added: 1 }), counts({ tasks_done: 2 }));
    expect(text).toBe("This week you completed 5 tasks and added 1 photo. That's 3 more tasks than last week.");
  });
  it("does not compare against an empty last week", () => {
    expect(weekHeadline(counts({ tasks_done: 1 }), counts())).toBe("This week you completed 1 task.");
  });
});

describe("streakText", () => {
  it("celebrates a record", () => expect(streakText(4, 4)).toContain("best yet"));
  it("shows the best when behind it", () => expect(streakText(2, 6)).toBe("2 days in a row (best 6)"));
  it("nudges after a break", () => expect(streakText(0, 3)).toContain("Start a new one"));
  it("has a neutral empty state", () => expect(streakText(0, 0)).toBe("No streak yet"));
});

describe("dayLabel", () => {
  it("describes the day for screen readers and tooltips", () => {
    expect(dayLabel(day("2026-06-10", { total: 3, tasks_done: 2, photos_added: 1 }))).toBe("Wed, 10 Jun: 2 tasks done, 1 photo");
    expect(dayLabel(day("2026-06-10"))).toBe("Wed, 10 Jun: nothing logged");
  });
});
