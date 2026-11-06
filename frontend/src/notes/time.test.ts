import { describe, expect, it } from "vitest";
import { dayOfNote, fromInput, groupNotesByDay, toInput } from "./time";

describe("note times", () => {
  it("round-trips through a datetime-local value", () => {
    expect(toInput(fromInput("2026-11-02T09:30"))).toBe("2026-11-02T09:30");
  });

  it("groups by local day, newest day first, keeping several a day", () => {
    const at = (s: string) => ({ noted_at: new Date(s).toISOString(), body: s });
    const days = groupNotesByDay([at("2026-11-02T18:00"), at("2026-11-02T08:00"), at("2026-11-01T12:00")]);
    expect(days.map((d) => d.date)).toEqual(["2026-11-02", "2026-11-01"]);
    expect(days[0].items).toHaveLength(2);
    expect(dayOfNote(days[0].items[0].noted_at)).toBe("2026-11-02");
  });
});
