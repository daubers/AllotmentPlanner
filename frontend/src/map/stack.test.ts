import { describe, expect, it } from "vitest";
import { byStack, edgeZ, inRing, nextBeneath, type Stacked } from "./stack";

const f = (id: number, kind: Stacked["kind"], z = 0): Stacked => ({ id, kind, z });

describe("stacking", () => {
  it("puts boundaries at the bottom and trees on top by default, whatever the age", () => {
    const items = [f(1, "tree"), f(2, "bed"), f(3, "boundary"), f(4, "path")];
    expect(items.sort(byStack).map((i) => i.kind)).toEqual(["boundary", "path", "bed", "tree"]);
  });

  it("lets a chosen z beat the kind, then falls back to age", () => {
    const items = [f(1, "bed"), f(2, "boundary", 1), f(3, "bed")];
    expect(items.sort(byStack).map((i) => i.id)).toEqual([1, 3, 2]);
  });

  it("finds a z above or below everything else", () => {
    const items = [f(1, "bed", 2), f(2, "bed", -1), f(3, "bed")];
    expect(edgeZ(items, 3, "top")).toBe(3);
    expect(edgeZ(items, 3, "bottom")).toBe(-2);
    expect(edgeZ([f(1, "bed")], 1, "top")).toBe(0);
  });
});

describe("hit testing", () => {
  const square: [number, number][] = [[0, 0], [4, 0], [4, 4], [0, 4]];
  it("knows inside from outside", () => {
    expect(inRing([2, 2], square)).toBe(true);
    expect(inRing([5, 2], square)).toBe(false);
  });

  it("walks down a stack and wraps round", () => {
    expect(nextBeneath([5, 3, 1], null)).toBe(5);
    expect(nextBeneath([5, 3, 1], 5)).toBe(3);
    expect(nextBeneath([5, 3, 1], 1)).toBe(5);
    expect(nextBeneath([5, 3, 1], 9)).toBe(5);
    expect(nextBeneath([], 1)).toBeNull();
  });
});
