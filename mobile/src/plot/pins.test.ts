import type { Task } from "../tasks/model";
import { jobsFor, pinsFor } from "./pins";
import type { PlotShape } from "./shapes";

const bed: PlotShape = { id: 1, kind: "bed", name: "Bed A", type: "area", points: [[0, 0], [2, 0], [2, 2], [0, 2]], radiusM: null };
const shed: PlotShape = { id: 2, kind: "shed", name: "", type: "area", points: [[5, 5], [6, 5], [6, 6]], radiusM: null };
const t = (id: number, extra: Partial<Task>): Task => ({ id, title: `job ${id}`, status: "todo", due_date: null, feature_id: null, location: null, ...extra });
const TODAY = "2026-11-03";

describe("pinsFor", () => {
  it("pins due and late jobs on their shape, one pin per shape, red if any is late", () => {
    const pins = pinsFor([bed, shed], [t(1, { feature_id: 1, due_date: TODAY }), t(2, { feature_id: 1, due_date: "2026-11-01" }), t(3, { feature_id: 2 })], TODAY);
    expect(pins).toHaveLength(2);
    const a = pins.find((p) => p.selection.kind === "shape" && p.selection.id === 1)!;
    expect([a.count, a.late, a.point]).toEqual([2, true, [1, 1]]);
    expect(pins.find((p) => p.selection.kind === "shape" && p.selection.id === 2)!.late).toBe(false);
  });

  it("ignores future, done and unplaced jobs", () => {
    const pins = pinsFor(
      [bed],
      [t(1, { feature_id: 1, due_date: "2026-11-04" }), t(2, { feature_id: 1, status: "done" }), t(3, {}), t(4, { feature_id: 99, due_date: TODAY })],
      TODAY,
    );
    expect(pins).toEqual([]);
  });

  it("pins a job that only has a point there, and groups jobs at the same point", () => {
    const loc = { type: "Point", coordinates: [3, 4] };
    const pins = pinsFor([bed], [t(1, { location: loc, due_date: TODAY }), t(2, { location: loc })], TODAY);
    expect(pins).toHaveLength(1);
    expect([pins[0].count, pins[0].point, pins[0].selection.kind]).toEqual([2, [3, 4], "spot"]);
  });
});

describe("jobsFor", () => {
  const tasks = [t(1, { feature_id: 1, due_date: "2026-12-01" }), t(2, { feature_id: 1, due_date: TODAY }), t(3, { feature_id: 1 }), t(4, { feature_id: 1, status: "done" }), t(5, { feature_id: 2 })];

  it("lists every open job linked to the shape, soonest first and undated last", () => {
    expect(jobsFor({ kind: "shape", id: 1 }, tasks).map((x) => x.id)).toEqual([2, 1, 3]);
  });

  it("finds jobs pinned at a spot, and nothing for no selection", () => {
    const loc = { type: "Point", coordinates: [3, 4] };
    expect(jobsFor({ kind: "spot", key: "3.000000,4.000000" }, [t(1, { location: loc })]).map((x) => x.id)).toEqual([1]);
    expect(jobsFor(null, tasks)).toEqual([]);
  });
});
