import { centreOf, type LonLat } from "../beds/geometry";
import type { Task } from "../tasks/model";
import type { PlotShape } from "./shapes";

/** What is selected on the map: a drawn shape, or a spot where a job was pinned away from any shape. */
export type Selection = { kind: "shape"; id: number } | { kind: "spot"; key: string };

export type Pin = { key: string; point: LonLat; count: number; late: boolean; selection: Selection };

const isOpen = (t: Task) => t.status !== "done";
const spotKey = (p: LonLat) => `${p[0].toFixed(6)},${p[1].toFixed(6)}`;

/** Where a shape's pin sits: the middle of its extent (the point itself for a point). */
export const anchorOf = (s: PlotShape): LonLat => (s.points.length === 1 ? s.points[0] : centreOf(s.points));

function pointOf(t: Task): LonLat | null {
  const l = t.location as { type?: string; coordinates?: number[] } | null | undefined;
  return l?.type === "Point" && Array.isArray(l.coordinates) && l.coordinates.length >= 2 ? [l.coordinates[0], l.coordinates[1]] : null;
}

/** Open jobs due today or earlier, which is what the Jobs tile counts. */
export function dueJobs(tasks: Task[] | undefined, today: string): Task[] {
  return (tasks ?? []).filter((t) => isOpen(t) && (!t.due_date || t.due_date <= today));
}

/**
 * One pin per shape (or per pinned spot) that has jobs due. A job tied to a shape pins at the shape; a job with
 * only a point pins there; a job tied to nothing on the map has no pin. Late jobs turn the pin red.
 */
export function pinsFor(shapes: PlotShape[], tasks: Task[] | undefined, today: string): Pin[] {
  const byShape = new Map(shapes.map((s) => [s.id, s]));
  const pins = new Map<string, Pin>();
  for (const t of dueJobs(tasks, today)) {
    const late = !!t.due_date && t.due_date < today;
    const shape = t.feature_id != null ? byShape.get(t.feature_id) : undefined;
    const spot = shape ? null : pointOf(t);
    if (!shape && !spot) continue;
    const key = shape ? `shape:${shape.id}` : `spot:${spotKey(spot!)}`;
    const pin = pins.get(key) ?? {
      key,
      point: shape ? anchorOf(shape) : spot!,
      count: 0,
      late: false,
      selection: shape ? ({ kind: "shape", id: shape.id } as Selection) : ({ kind: "spot", key: spotKey(spot!) } as Selection),
    };
    pin.count += 1;
    pin.late = pin.late || late;
    pins.set(key, pin);
  }
  return [...pins.values()];
}

/** The open jobs linked to what is selected, soonest first (undated last). */
export function jobsFor(selection: Selection | null, tasks: Task[] | undefined): Task[] {
  if (!selection) return [];
  const mine = (tasks ?? []).filter((t) => {
    if (!isOpen(t)) return false;
    if (selection.kind === "shape") return t.feature_id === selection.id;
    const p = t.feature_id == null ? pointOf(t) : null;
    return !!p && spotKey(p) === selection.key;
  });
  return mine.sort((a, b) => (a.due_date ?? "9999").localeCompare(b.due_date ?? "9999"));
}
