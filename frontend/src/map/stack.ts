import type { Kind } from "./kinds";

/** Where each kind sits when nothing says otherwise: areas underneath, things standing on them above. */
const KIND_RANK: Record<Kind, number> = {
  boundary: 0,
  water: 1,
  path: 2,
  bed: 3,
  compost: 4,
  other: 5,
  shed: 6,
  tree: 7,
};

export type Stacked = { id: number; kind: Kind; z: number };

/** Bottom first: the person's own order, then the kind's usual place, then oldest first. */
export function byStack(a: Stacked, b: Stacked): number {
  return a.z - b.z || (KIND_RANK[a.kind] ?? 5) - (KIND_RANK[b.kind] ?? 5) || a.id - b.id;
}

/** A z that puts a feature above everything else (or below, for `bottom`). */
export function edgeZ(items: Stacked[], id: number, edge: "top" | "bottom"): number {
  const others = items.filter((i) => i.id !== id).map((i) => i.z);
  if (others.length === 0) return 0;
  return edge === "top" ? Math.max(...others) + 1 : Math.min(...others) - 1;
}

type Pt = [number, number];

/** Is the point inside the ring? (Planar test: fine at the size of an allotment.) */
export function inRing(p: Pt, ring: Pt[]): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    if (yi > p[1] !== yj > p[1] && p[0] < ((xj - xi) * (p[1] - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

/** The next feature down in a stack (top first), wrapping to the top; the top one if none is current. */
export function nextBeneath(stackTopFirst: number[], current: number | null): number | null {
  if (stackTopFirst.length === 0) return null;
  const at = current === null ? -1 : stackTopFirst.indexOf(current);
  return stackTopFirst[(at + 1) % stackTopFirst.length];
}
