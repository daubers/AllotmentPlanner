import { ringOf, type LonLat } from "../beds/geometry";

/** What the web map calls each kind of shape, and the colour it draws it in. */
export const KIND_COLOURS: Record<string, string> = {
  bed: "#3f8f3f",
  path: "#a08c6a",
  shed: "#8a5a3c",
  tree: "#1f6b3a",
  water: "#2f7fc1",
  compost: "#6b4f2a",
  boundary: "#444444",
  other: "#7a5ea8",
};
export const colourForKind = (kind: string | undefined): string => KIND_COLOURS[kind ?? ""] ?? KIND_COLOURS.other;

export type PlotShape = {
  id: number;
  kind: string;
  name: string;
  type: "area" | "line" | "point";
  points: LonLat[];
  /** For a circle drawn on the map (a point with a radius). */
  radiusM: number | null;
};

/** Flat shapes from the allotment's GeoJSON features; anything without usable geometry is left out. */
export function shapesOf(features: any[] | undefined): PlotShape[] {
  const out: PlotShape[] = [];
  for (const f of features ?? []) {
    const g = f?.geometry;
    const base = { id: f.id as number, kind: (f.properties?.kind as string) || "other", name: (f.properties?.name as string) || "" };
    if (g?.type === "Polygon") {
      const ring = ringOf(g);
      if (ring.length >= 3) out.push({ ...base, type: "area", points: ring, radiusM: null });
    } else if (g?.type === "LineString" && Array.isArray(g.coordinates) && g.coordinates.length >= 2) {
      out.push({ ...base, type: "line", points: g.coordinates.map((c: number[]) => [c[0], c[1]] as LonLat), radiusM: null });
    } else if (g?.type === "Point" && Array.isArray(g.coordinates)) {
      const r = Number(f.properties?.radius_m);
      out.push({ ...base, type: "point", points: [[g.coordinates[0], g.coordinates[1]]], radiusM: Number.isFinite(r) && r > 0 ? r : null });
    }
  }
  return out;
}

/** Every point of every shape, for fitting the picture to the plot. A circle also contributes its extent. */
export function extentPoints(shapes: PlotShape[]): LonLat[] {
  const M_PER_DEG = 111_320;
  const pts: LonLat[] = [];
  for (const s of shapes) {
    pts.push(...s.points);
    if (s.type === "point" && s.radiusM) {
      const [lon, lat] = s.points[0];
      const dLat = s.radiusM / M_PER_DEG;
      const dLon = s.radiusM / (M_PER_DEG * Math.max(Math.cos((lat * Math.PI) / 180), 0.01));
      pts.push([lon - dLon, lat - dLat], [lon + dLon, lat + dLat]);
    }
  }
  return pts;
}
