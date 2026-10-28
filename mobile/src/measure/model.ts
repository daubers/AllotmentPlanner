import type { LengthUnit } from "./units";

export type Item = {
  id: number;
  feature_id: number;
  feature_name: string;
  feature_kind: string;
  kind: "edge" | "diagonal" | "radius" | "custom";
  a: number;
  b: number;
  label: string;
  drawn_m: number | null;
  value_m: number | null;
  note: string;
  skipped: boolean;
  stale: boolean;
};

export type FeatureProgress = { id: number; name: string; kind: string; corners: number; measured: number; total: number };

export type Checklist = {
  length_unit: LengthUnit;
  items: Item[];
  features: FeatureProgress[];
  total: number;
  measured: number;
};

/** The next item still to measure after this one, going round the list. */
export function nextToMeasure(items: Item[], afterId: number): Item | null {
  const todo = items.filter((i) => !i.stale && !i.skipped && i.value_m === null);
  if (!todo.length) return null;
  const order = items.map((i) => i.id);
  const here = order.indexOf(afterId);
  return todo.find((i) => order.indexOf(i.id) > here) ?? todo.find((i) => i.id !== afterId) ?? null;
}
