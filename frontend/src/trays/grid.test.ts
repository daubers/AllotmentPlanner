import { describe, expect, it } from "vitest";
import { cellMap, colourIndex, daysSince, describeCell, key, posOf, selectAll, summarise, toggle, toggleCol, toggleRow } from "./grid";

describe("selection", () => {
  it("toggles single cells", () => {
    const one = toggle(new Set(), key(1, 2));
    expect([...one]).toEqual(["1,2"]);
    expect(toggle(one, key(1, 2)).size).toBe(0);
  });
  it("selects a whole row, then deselects it", () => {
    const row = toggleRow(new Set(), 1, 3);
    expect([...row].sort()).toEqual(["1,0", "1,1", "1,2"]);
    expect(toggleRow(row, 1, 3).size).toBe(0);
  });
  it("completes a partly selected column instead of clearing it", () => {
    const part = toggle(new Set(), key(0, 2));
    expect([...toggleCol(part, 2, 3)].sort()).toEqual(["0,2", "1,2", "2,2"]);
  });
  it("selects everything, row by row", () => {
    expect(selectAll(2, 3).size).toBe(6);
    expect(posOf("1,2")).toEqual({ row: 1, col: 2 });
  });
});

describe("colours", () => {
  const kinds = [{ packet_id: 5 }, { packet_id: 9 }];
  it("follows the order of the kinds", () => {
    expect(colourIndex(5, kinds)).toBe(0);
    expect(colourIndex(9, kinds)).toBe(1);
    expect(colourIndex(null, kinds)).toBe(-1);
    expect(colourIndex(77, kinds)).toBe(-1);
  });
  it("wraps round the palette", () => {
    const many = Array.from({ length: 10 }, (_, i) => ({ packet_id: i }));
    expect(colourIndex(9, many)).toBe(1);
  });
});

describe("wording", () => {
  it("summarises counts, leaving out zeros", () => {
    expect(summarise({ sown: 5, germinated: 2, failed: 0, planted_out: 0, empty: 4 })).toBe("5 sown, 2 germinated, 4 empty");
    expect(summarise(undefined)).toBe("");
  });
  it("describes cells for screen readers", () => {
    expect(describeCell(0, 1, undefined)).toBe("Row 1, column 2: empty");
    const cell = cellMap([{ row: 0, col: 1, status: "germinated" }]).get(key(0, 1));
    expect(describeCell(0, 1, cell, "Tomato")).toBe("Row 1, column 2: Tomato, germinated");
  });
  it("counts days since a date", () => {
    expect(daysSince("2026-03-01", new Date(2026, 2, 13, 15, 0))).toBe(12);
    expect(daysSince(null)).toBeNull();
  });
});
