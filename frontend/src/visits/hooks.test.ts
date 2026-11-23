import { describe, expect, it } from "vitest";
import { googleCalendarUrl } from "./hooks";
import type { Visit } from "./hooks";

function visit(overrides: Partial<Visit> = {}): Visit {
  return {
    id: 1,
    title: "Morning round",
    notes: "bring gloves",
    starts_at: "2026-11-07T09:00:00Z",
    duration_minutes: 90,
    task_ids: [],
    ...overrides,
  };
}

describe("googleCalendarUrl", () => {
  it("builds a prefilled TEMPLATE link with the visit's title, window and notes", () => {
    const url = new URL(googleCalendarUrl(visit()));
    expect(url.origin + url.pathname).toBe("https://calendar.google.com/calendar/render");
    expect(url.searchParams.get("action")).toBe("TEMPLATE");
    expect(url.searchParams.get("text")).toBe("Morning round");
    expect(url.searchParams.get("dates")).toBe("20261107T090000Z/20261107T103000Z");
    expect(url.searchParams.get("details")).toBe("bring gloves");
  });

  it("defaults a missing duration to 120 minutes", () => {
    const url = new URL(googleCalendarUrl(visit({ duration_minutes: undefined })));
    expect(url.searchParams.get("dates")).toBe("20261107T090000Z/20261107T110000Z");
  });

  it("adds what to bring after the notes", () => {
    const bring = [{ id: 1, name: "Border spade" }, { id: 2, name: "Dibber" }];
    const url = new URL(googleCalendarUrl(visit({ bring: bring as Visit["bring"] })));
    expect(url.searchParams.get("details")).toBe("bring gloves\n\nBring: Border spade, Dibber");
  });

  it("has only the bring line when there are no notes, and none when there is nothing to bring", () => {
    const only = new URL(googleCalendarUrl(visit({ notes: "", bring: [{ id: 1, name: "Spade" }] as Visit["bring"] })));
    expect(only.searchParams.get("details")).toBe("Bring: Spade");
    expect(new URL(googleCalendarUrl(visit({ bring: [] }))).searchParams.get("details")).toBe("bring gloves");
  });
});
