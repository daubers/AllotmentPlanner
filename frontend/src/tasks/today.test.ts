import { describe, expect, it } from "vitest";
import { buildSketch } from "../map/sketch";
import type { Task } from "./group";
import { daysBetween, flatten, groupByLocation, longDate } from "./today";

const task = (id: number, extra: Partial<Task> = {}): Task => ({ id, title: `t${id}`, status: "todo", ...extra }) as Task;
const features = [
  { id: 1, properties: { name: "Bed 1", kind: "bed" } },
  { id: 2, properties: { name: "", kind: "tree" } },
];

describe("groupByLocation", () => {
  it("orders sections by map order, then pinned-on-map, then anywhere", () => {
    const sections = groupByLocation(
      [task(1), task(2, { feature_id: 2 }), task(3, { location: { type: "Point", coordinates: [0, 0] } }), task(4, { feature_id: 1 }), task(5, { feature_id: 1 })],
      features,
    );
    expect(sections.map((s) => s.title)).toEqual(["Bed 1", "Unnamed tree", "Pinned on the map", "Anywhere"]);
    expect(sections[0].tasks.map((t) => t.id)).toEqual([4, 5]);
    expect(flatten(sections).map((t) => t.id)).toEqual([4, 5, 2, 3, 1]);
  });

  it("never drops a task pinned to an unknown feature", () => {
    const sections = groupByLocation([task(1, { feature_id: 99 })], features);
    expect(sections).toEqual([{ title: "Anywhere", tasks: [expect.objectContaining({ id: 1 })] }]);
  });

  it("returns no sections for no tasks", () => {
    expect(groupByLocation([], features)).toEqual([]);
  });
});

describe("dates", () => {
  it("counts days between dates across month and DST boundaries", () => {
    expect(daysBetween("2026-10-30", "2026-11-02")).toBe(3);
    expect(daysBetween("2026-03-28", "2026-03-30")).toBe(2); // UK clocks change on the 29th
    expect(daysBetween("2026-11-02", "2026-11-02")).toBe(0);
  });

  it("formats a long UK date", () => {
    expect(longDate("2026-11-02")).toBe("Monday 2 November 2026");
  });
});

describe("buildSketch", () => {
  const bed = {
    id: 1,
    geometry: { type: "Polygon", coordinates: [[[-1, 51], [-1, 51.001], [-0.999, 51.001], [-0.999, 51], [-1, 51]]] },
    properties: { name: "Bed 1", kind: "bed" },
  };

  it("fits everything inside the canvas with north up", () => {
    const s = buildSketch([bed], [], { width: 400, height: 300, padding: 20 });
    expect(s.shapes).toHaveLength(1);
    const nums = (s.shapes[0] as { d: string }).d.match(/-?\d+\.\d/g)!.map(Number);
    const xs = nums.filter((_, i) => i % 2 === 0);
    const ys = nums.filter((_, i) => i % 2 === 1);
    expect(Math.min(...xs)).toBeGreaterThanOrEqual(20 - 0.1);
    expect(Math.max(...xs)).toBeLessThanOrEqual(380 + 0.1);
    expect(Math.min(...ys)).toBeGreaterThanOrEqual(20 - 0.1);
    expect(Math.max(...ys)).toBeLessThanOrEqual(280 + 0.1);
  });

  it("numbers pins in task order and places a feature's pin at its centre", () => {
    const s = buildSketch([bed], [task(7, { feature_id: 1 }), task(8)], { width: 400, height: 300, padding: 20 });
    expect(s.pins).toEqual([expect.objectContaining({ n: 1, taskId: 7 })]); // task 8 has no position
    expect(s.pins[0].x).toBeCloseTo(200, 0);
    expect(s.pins[0].y).toBeCloseTo(150, 0);
  });

  it("fans out pins that share a spot", () => {
    const s = buildSketch([bed], [task(1, { feature_id: 1 }), task(2, { feature_id: 1 })]);
    expect(s.pins[1].x - s.pins[0].x).toBe(26);
    expect(s.pins[1].y).toBe(s.pins[0].y);
  });

  it("draws a circle feature to scale and copes with a single point", () => {
    const tree = { id: 2, geometry: { type: "Point", coordinates: [-1, 51] }, properties: { kind: "tree", radius_m: 2 } };
    const s = buildSketch([tree], []);
    expect(s.shapes[0]).toMatchObject({ type: "point" });
    expect((s.shapes[0] as { r: number }).r).toBeGreaterThan(3);
    expect(buildSketch([], [])).toEqual({ width: 640, height: 420, shapes: [], pins: [] });
  });
});
