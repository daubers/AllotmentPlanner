import { describe, expect, it } from "vitest";
import { ago, duration, jobTime } from "./format";

const now = new Date("2026-11-01T12:00:00Z").getTime();

describe("ago", () => {
  it("says how long ago, in the biggest sensible unit", () => {
    expect(ago("2026-11-01T11:59:58Z", now)).toBe("just now");
    expect(ago("2026-11-01T11:59:00Z", now)).toBe("60 s ago");
    expect(ago("2026-11-01T11:50:00Z", now)).toBe("10 min ago");
    expect(ago("2026-11-01T07:00:00Z", now)).toBe("5 h ago");
    expect(ago("2026-10-27T12:00:00Z", now)).toBe("5 days ago");
  });
  it("handles a missing time", () => {
    expect(ago(null, now)).toBe("never");
  });
});

describe("duration", () => {
  it("formats lengths of time", () => {
    expect(duration(null)).toBe("–");
    expect(duration(45)).toBe("45 s");
    expect(duration(600)).toBe("10 min");
    expect(duration(3 * 3600 + 300)).toBe("3 h 05 min");
  });
});

describe("jobTime", () => {
  it("uses the finish time, or now while running, and nothing if it has not started", () => {
    const created_at = "2026-11-01T10:00:00Z";
    expect(jobTime({ created_at }, now)).toBeNull();
    expect(jobTime({ created_at, started_at: "2026-11-01T11:00:00Z", finished_at: "2026-11-01T11:10:00Z" }, now)).toBe(600);
    expect(jobTime({ created_at, started_at: "2026-11-01T11:30:00Z" }, now)).toBe(1800);
  });
});
