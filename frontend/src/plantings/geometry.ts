/** Shapes in a bed, drawn on a flat sketch: lon/lat in, SVG pixels out, north up. No map tiles. */
export type LonLat = [number, number];
export type Xy = [number, number];

const M_PER_DEG = 111_320;

export type Frame = {
  width: number;
  height: number;
  project(p: LonLat): Xy;
  unproject(p: Xy): LonLat;
  pxPerMetre: number;
};

/** A frame that fits ``ring`` (the bed) in a ``width`` x ``height`` sketch with some padding. */
export function frameFor(ring: LonLat[], { width = 640, height = 360, padding = 24 } = {}): Frame {
  const lons = ring.map((p) => p[0]);
  const lats = ring.map((p) => p[1]);
  const [minLon, maxLon, minLat, maxLat] = [Math.min(...lons), Math.max(...lons), Math.min(...lats), Math.max(...lats)];
  const kx = Math.cos((((minLat + maxLat) / 2) * Math.PI) / 180);
  const spanX = Math.max((maxLon - minLon) * kx, 1 / M_PER_DEG);
  const spanY = Math.max(maxLat - minLat, 1 / M_PER_DEG);
  const scale = Math.min((width - 2 * padding) / spanX, (height - 2 * padding) / spanY); // px per degree
  const offX = (width - spanX * scale) / 2;
  const offY = (height - spanY * scale) / 2;
  return {
    width,
    height,
    pxPerMetre: scale / M_PER_DEG,
    project: ([lon, lat]) => [offX + (lon - minLon) * kx * scale, height - (offY + (lat - minLat) * scale)],
    unproject: ([x, y]) => [minLon + (x - offX) / (kx * scale), minLat + (height - y - offY) / scale],
  };
}

/** Metres east and north of the ring's first point, for distance and area sums. */
function flat(ring: LonLat[]): Xy[] {
  const [lon0, lat0] = ring[0];
  const kx = Math.cos((lat0 * Math.PI) / 180);
  return ring.map(([lon, lat]) => [(lon - lon0) * kx * M_PER_DEG, (lat - lat0) * M_PER_DEG]);
}

export function areaM2(ring: LonLat[]): number {
  if (ring.length < 3) return 0;
  const pts = flat(ring);
  let sum = 0;
  for (let i = 0; i < pts.length; i++) {
    const [x1, y1] = pts[i];
    const [x2, y2] = pts[(i + 1) % pts.length];
    sum += x1 * y2 - x2 * y1;
  }
  return Math.abs(sum) / 2;
}

export function pointInRing(p: LonLat, ring: LonLat[]): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    if (yi > p[1] !== yj > p[1] && p[0] < ((xj - xi) * (p[1] - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

/** Shortest distance in metres from ``p`` to the ring's edge. */
export function distanceToEdgeM(p: LonLat, ring: LonLat[]): number {
  const all = flat([ring[0], ...ring.slice(1), p]);
  const pt = all[all.length - 1];
  const pts = all.slice(0, -1);
  let best = Infinity;
  for (let i = 0; i < pts.length; i++) {
    const [ax, ay] = pts[i];
    const [bx, by] = pts[(i + 1) % pts.length];
    const dx = bx - ax;
    const dy = by - ay;
    const t = dx || dy ? Math.max(0, Math.min(1, ((pt[0] - ax) * dx + (pt[1] - ay) * dy) / (dx * dx + dy * dy))) : 0;
    best = Math.min(best, Math.hypot(pt[0] - (ax + t * dx), pt[1] - (ay + t * dy)));
  }
  return best;
}

/** Whether a clicked point is in the bed, or close enough to its edge that the server will accept it. */
export function withinBed(p: LonLat, bed: LonLat[], toleranceM = 0.25): boolean {
  return pointInRing(p, bed) || distanceToEdgeM(p, bed) <= toleranceM;
}

/** The ring of a GeoJSON Polygon without its closing point. */
export function ringOf(polygon: { coordinates?: unknown } | null | undefined): LonLat[] {
  const ring = ((polygon?.coordinates as LonLat[][] | undefined) ?? [])[0] ?? [];
  return ring.length > 1 && ring[0][0] === ring[ring.length - 1][0] && ring[0][1] === ring[ring.length - 1][1] ? ring.slice(0, -1) : ring;
}

export function polygonOf(ring: LonLat[]): { type: "Polygon"; coordinates: LonLat[][] } {
  return { type: "Polygon", coordinates: [[...ring, ring[0]]] };
}

export const PALETTE = ["#4c9a4f", "#e0a526", "#3f87c6", "#d1625b", "#8c6bb1", "#3fa5a0", "#a89a3e", "#7a7a7a"];
export const colourOf = (packetId: number | null | undefined): string =>
  packetId == null ? PALETTE[7] : PALETTE[packetId % PALETTE.length];

/** "2.4 m²" or "35 cm²-ish": plain wording for an area. */
export function areaLabel(m2: number): string {
  return m2 >= 10 ? `${Math.round(m2)} m²` : `${m2.toFixed(1)} m²`;
}
