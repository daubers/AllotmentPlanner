import type { PlanBed } from "./hooks";

export type Clash = { from: string; to: string; peak_m2: number; over_m2: number; item_ids: number[] };

/** Join stretches that run on from one another (one ends the day the next begins) into one, keeping the worst. */
export function mergeConflicts(conflicts: PlanBed["conflicts"] = []): Clash[] {
  const out: Clash[] = [];
  const sorted = [...conflicts].sort((a, b) => (a.from! < b.from! ? -1 : a.from! > b.from! ? 1 : 0));
  for (const c of sorted) {
    const last = out[out.length - 1];
    if (last && last.to >= c.from!) {
      if (c.to! > last.to) last.to = c.to!;
      last.peak_m2 = Math.max(last.peak_m2, c.used_m2 ?? 0);
      last.over_m2 = Math.max(last.over_m2, c.over_m2 ?? 0);
      last.item_ids = [...new Set([...last.item_ids, ...(c.item_ids ?? [])])].sort((a, b) => a - b);
    } else {
      out.push({ from: c.from!, to: c.to!, peak_m2: c.used_m2 ?? 0, over_m2: c.over_m2 ?? 0, item_ids: [...(c.item_ids ?? [])] });
    }
  }
  return out;
}
