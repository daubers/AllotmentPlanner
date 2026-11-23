import { describe, expect, it } from "vitest";
import { mergeConflicts } from "./conflicts";

const c = (from: string, to: string, used: number, over: number, ids: number[]) => ({ from, to, used_m2: used, over_m2: over, item_ids: ids });

describe("mergeConflicts", () => {
  it("is empty for none", () => {
    expect(mergeConflicts([])).toEqual([]);
    expect(mergeConflicts(undefined)).toEqual([]);
  });

  it("joins stretches that run on, keeping the worst and everyone involved", () => {
    const merged = mergeConflicts([
      c("2027-04-26", "2027-05-10", 120, 20, [1, 2]),
      c("2027-05-10", "2027-05-20", 150, 50, [1, 2, 3]),
      c("2027-05-20", "2027-06-03", 205, 105, [2, 3, 4]),
    ]);
    expect(merged).toEqual([{ from: "2027-04-26", to: "2027-06-03", peak_m2: 205, over_m2: 105, item_ids: [1, 2, 3, 4] }]);
  });

  it("keeps separate runs apart, in date order", () => {
    const merged = mergeConflicts([c("2027-08-01", "2027-08-10", 110, 10, [5]), c("2027-04-01", "2027-04-10", 120, 20, [1])]);
    expect(merged.map((m) => [m.from, m.to])).toEqual([["2027-04-01", "2027-04-10"], ["2027-08-01", "2027-08-10"]]);
  });
});
