import { combineLocalDateTime, bringLabel } from "./model";

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

describe("bringLabel", () => {
  it("is just the name for something a job needs", () => {
    expect(bringLabel({ name: "Border spade", source: "task" })).toBe("Border spade");
    expect(bringLabel({ name: "Wheelbarrow", source: "extra" })).toBe("Wheelbarrow");
  });

  it("says when it was only suggested, or is out of action", () => {
    expect(bringLabel({ name: "Dibber", source: "suggested" })).toBe("Dibber (suggested)");
    expect(bringLabel({ name: "Old hoe", source: "task", status: "out_of_action" })).toBe("Old hoe (out of action)");
    expect(bringLabel({ name: "Rake", source: "suggested", status: "out_of_action" })).toBe("Rake (suggested, out of action)");
  });

  it("copes with a missing name", () => {
    expect(bringLabel({})).toBe("Equipment");
  });
});
