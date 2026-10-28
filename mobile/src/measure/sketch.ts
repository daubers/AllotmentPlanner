/** A small drawing of a shape with its corners numbered, so you know which two you are measuring. */

export type Point = { x: number; y: number };

const M_PER_DEG_LAT = 111_195;

/** (lon, lat) corners to metres east/north of the first-corner-centred origin. */
export function toLocal(corners: [number, number][]): Point[] {
  const lat0 = corners.reduce((s, c) => s + c[1], 0) / corners.length;
  const lng0 = corners.reduce((s, c) => s + c[0], 0) / corners.length;
  const mPerLng = M_PER_DEG_LAT * Math.cos((lat0 * Math.PI) / 180);
  return corners.map(([lng, lat]) => ({ x: (lng - lng0) * mPerLng, y: (lat - lat0) * M_PER_DEG_LAT }));
}

export type Layout = {
  /** Corner positions in the drawing (y grows downwards, north is up). */
  points: Point[];
  width: number;
  height: number;
  /** Where to put each corner's number: pushed outwards from the middle. */
  labels: Point[];
};

/** Fit points into a width x height drawing with padding, keeping their proportions. */
export function layout(points: Point[], width: number, height: number, pad = 28): Layout {
  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const spanX = maxX - minX;
  const spanY = maxY - minY;
  // A shape with no width (or height) is centred on that axis instead of stretched to fill it.
  const fits = [
    spanX > 1e-6 ? (width - 2 * pad) / spanX : Infinity,
    spanY > 1e-6 ? (height - 2 * pad) / spanY : Infinity,
  ];
  const scale = Math.min(...fits) === Infinity ? 1 : Math.min(...fits);
  const offX = (width - spanX * scale) / 2;
  const offY = (height - spanY * scale) / 2;
  const placed = points.map((p) => ({ x: offX + (p.x - minX) * scale, y: offY + (maxY - p.y) * scale }));
  const cx = placed.reduce((s, p) => s + p.x, 0) / placed.length;
  const cy = placed.reduce((s, p) => s + p.y, 0) / placed.length;
  const labels = placed.map((p) => {
    const dx = p.x - cx;
    const dy = p.y - cy;
    const len = Math.hypot(dx, dy) || 1;
    return { x: p.x + (dx / len) * 16, y: p.y + (dy / len) * 16 };
  });
  return { points: placed, width, height, labels };
}

/** Both outlines drawn on one scale, so drawn and corrected can be compared. */
export function layoutTogether(sets: Point[][], width: number, height: number, pad = 28): Layout[] {
  const all = sets.flat();
  const joined = layout(all, width, height, pad);
  let at = 0;
  return sets.map((set) => {
    const pts = joined.points.slice(at, at + set.length);
    const labels = joined.labels.slice(at, at + set.length);
    at += set.length;
    return { points: pts, width, height, labels };
  });
}
