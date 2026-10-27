import type { Task } from "../tasks/group";
import { colourFor } from "./kinds";

type Coord = [number, number]; // [lon, lat]
type Geometry = { type: string; coordinates: unknown };
export type SketchFeature = {
  id: number;
  geometry: Geometry;
  properties: { name?: string; kind?: string; radius_m?: number | null };
};

type Coord2 = [number, number]; // [x, y] in sketch pixels
type Labelled = { label?: string; labelAt: Coord2 };
export type Shape =
  | ({ type: "polygon" | "line"; id: number; d: string; colour: string } & Labelled)
  | ({ type: "point"; id: number; x: number; y: number; r: number; colour: string } & Labelled);

export type Pin = { n: number; taskId: number; x: number; y: number };
export type Sketch = { width: number; height: number; shapes: Shape[]; pins: Pin[] };

const METRES_PER_DEGREE = 111_320;

function coords(g: Geometry): Coord[] {
  const c = g.coordinates as unknown;
  if (g.type === "Point") return [c as Coord];
  if (g.type === "LineString") return c as Coord[];
  if (g.type === "Polygon") return (c as Coord[][]).flat();
  return [];
}

/** Centre of the bounding box, matching where the map editor puts a feature's task pin. */
function centre(points: Coord[]): Coord {
  const lons = points.map((p) => p[0]);
  const lats = points.map((p) => p[1]);
  return [(Math.min(...lons) + Math.max(...lons)) / 2, (Math.min(...lats) + Math.max(...lats)) / 2];
}

/**
 * Draw the plot as a flat SVG sketch (equirectangular, north up), with a numbered pin for each
 * task, in the order given. No map tiles: it prints sharply and works offline.
 */
export function buildSketch(
  features: SketchFeature[],
  tasks: Task[],
  { width = 640, height = 420, padding = 28 } = {},
): Sketch {
  const featureById = new Map(features.map((f) => [f.id, f]));
  const taskPoint = (t: Task): Coord | null => {
    const loc = t.location as { coordinates?: Coord } | null | undefined;
    if (loc?.coordinates) return loc.coordinates;
    const f = t.feature_id != null ? featureById.get(t.feature_id) : undefined;
    const pts = f ? coords(f.geometry) : [];
    return pts.length ? centre(pts) : null;
  };

  const all: Coord[] = [...features.flatMap((f) => coords(f.geometry))];
  const taskPoints = tasks.map(taskPoint);
  for (const p of taskPoints) if (p) all.push(p);
  if (all.length === 0) return { width, height, shapes: [], pins: [] };

  const lons = all.map((p) => p[0]);
  const lats = all.map((p) => p[1]);
  const [minLon, maxLon, minLat, maxLat] = [Math.min(...lons), Math.max(...lons), Math.min(...lats), Math.max(...lats)];
  const kx = Math.cos((((minLat + maxLat) / 2) * Math.PI) / 180);
  // A single point has no extent; pretend the plot is ~20 m across so we still get a sane scale.
  const spanX = Math.max((maxLon - minLon) * kx, 20 / METRES_PER_DEGREE);
  const spanY = Math.max(maxLat - minLat, 20 / METRES_PER_DEGREE);
  const scale = Math.min((width - 2 * padding) / spanX, (height - 2 * padding) / spanY); // px per degree
  const offX = (width - spanX * scale) / 2;
  const offY = (height - spanY * scale) / 2;
  const project = ([lon, lat]: Coord): Coord2 => [
    offX + (lon - minLon) * kx * scale + ((spanX - (maxLon - minLon) * kx) * scale) / 2,
    height - (offY + (lat - minLat) * scale + ((spanY - (maxLat - minLat)) * scale) / 2),
  ];
  const pxPerMetre = scale / METRES_PER_DEGREE;
  const fmt = (p: Coord2) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`;

  const shapes: Shape[] = features.map((f): Shape | null => {
    const colour = colourFor(f.properties.kind);
    const label = f.properties.name || undefined;
    const g = f.geometry;
    if (g.type === "Polygon") {
      const ring = (g.coordinates as Coord[][])[0].map(project);
      const [cx, cy] = project(centre(coords(g)));
      // Below the centre, where the task pins for this bed sit.
      return { type: "polygon", id: f.id, d: `M${ring.map(fmt).join("L")}Z`, colour, label, labelAt: [cx, cy + 26] };
    }
    if (g.type === "LineString") {
      const [lx, ly] = project(centre(coords(g)));
      return { type: "line", id: f.id, d: `M${(g.coordinates as Coord[]).map(project).map(fmt).join("L")}`, colour, label, labelAt: [lx, ly - 6] };
    }
    if (g.type === "Point") {
      const [x, y] = project(g.coordinates as Coord);
      const r = f.properties.radius_m ? f.properties.radius_m * pxPerMetre : 4;
      const radius = Math.max(r, 3);
      return { type: "point", id: f.id, x, y, r: radius, colour, label, labelAt: [x, y + radius + 15] };
    }
    return null;
  }).filter((s): s is Shape => s !== null);

  // Pins at the same spot fan out sideways so every number stays readable.
  const seen = new Map<string, number>();
  const pins: Pin[] = [];
  tasks.forEach((t, i) => {
    const p = taskPoints[i];
    if (!p || t.id == null) return;
    const [x, y] = project(p);
    const key = `${Math.round(x)},${Math.round(y)}`;
    const k = seen.get(key) ?? 0;
    seen.set(key, k + 1);
    pins.push({ n: i + 1, taskId: t.id, x: x + k * 26, y });
  });

  return { width, height, shapes, pins };
}
