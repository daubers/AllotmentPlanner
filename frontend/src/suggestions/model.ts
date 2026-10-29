import type { components } from "../api/schema";

export type Suggestion = components["schemas"]["Suggestion"];
export type Sighting = components["schemas"]["Sighting"];

/** How many photos a row shows before "+N more". */
export const SHOWN_PHOTOS = 3;

/** The photos to show for a suggestion (best first, as the API sends them) and how many are left. */
export function photosOf(s: Pick<Suggestion, "sightings">, shown = SHOWN_PHOTOS): { shown: Sighting[]; more: number } {
  // A video sighting needs its second to show the right frame; ones saved without it are left out
  // rather than drawn over the wrong picture.
  const all = (s.sightings ?? []).filter((x) => x.outline && x.outline.length >= 3 && (x.kind !== "video" || x.at_s != null));
  return { shown: all.slice(0, shown), more: Math.max(0, all.length - shown) };
}

/** Where a video sighting's frame is: the video link opened at that second (a media fragment). */
export function frameSrc(x: Pick<Sighting, "url" | "kind" | "at_s">): string | undefined {
  return x.kind === "video" && x.at_s != null ? `${x.url}#t=${x.at_s}` : undefined;
}

/** An outline as the `points` of an SVG polygon in a 0..1 box (the photo is stretched to that box). */
export function outlinePoints(outline: number[][] | undefined): string {
  return (outline ?? []).map(([x, y]) => `${x},${y}`).join(" ");
}

/** How much to trust a detection, in words. Confidence is the detector's score, discounted when
 *  only one photo showed the object. */
export function confidenceWord(c: number | undefined): "likely" | "possible" | "unsure" {
  const v = c ?? 0;
  return v >= 0.6 ? "likely" : v >= 0.4 ? "possible" : "unsure";
}

/** Suggestions worth ticking by default: the ones the detector was reasonably sure about. */
export const tickedByDefault = (s: Suggestion): boolean => (s.confidence ?? 0) >= 0.4;

export function seenIn(s: Pick<Suggestion, "views">): string {
  const n = s.views ?? 1;
  return n === 1 ? "seen in 1 photo" : `seen in ${n} photos`;
}

/** A suggestion's shape in Leaflet's [lat, lng] order. */
export type Shape =
  | { type: "circle"; centre: [number, number]; radius: number }
  | { type: "polygon"; ring: [number, number][] };

export function shapeOf(s: Pick<Suggestion, "geometry" | "radius_m">): Shape | null {
  const g = s.geometry as { type?: string; coordinates?: unknown } | undefined;
  if (g?.type === "Point") {
    const [lng, lat] = g.coordinates as [number, number];
    return { type: "circle", centre: [lat, lng], radius: s.radius_m ?? 0.5 };
  }
  if (g?.type === "Polygon") {
    const ring = (g.coordinates as [number, number][][])[0].map(([lng, lat]) => [lat, lng] as [number, number]);
    return { type: "polygon", ring: ring.length > 1 && ring[0][0] === ring[ring.length - 1][0] && ring[0][1] === ring[ring.length - 1][1] ? ring.slice(0, -1) : ring };
  }
  return null;
}

/** Which suggestions are ticked once new data arrives: keep what the person chose, tick the
 *  rest by default. `known` is the set of ids already seen. */
export function mergeTicks(current: Set<number>, known: Set<number>, list: Suggestion[]): Set<number> {
  const next = new Set<number>();
  for (const s of list) {
    if (known.has(s.id!) ? current.has(s.id!) : tickedByDefault(s)) next.add(s.id!);
  }
  return next;
}

const METRES_PER_DEGREE = 111_000;

/** A suggestion's bounding box as [[south, west], [north, east]], padded a little so a single
 *  tiny circle still gives the map something to fit. */
export function suggestionBox(s: Pick<Suggestion, "geometry" | "radius_m">): [[number, number], [number, number]] | null {
  const shape = shapeOf(s);
  if (!shape) return null;
  if (shape.type === "circle") {
    const [lat, lng] = shape.centre;
    const dLat = shape.radius / METRES_PER_DEGREE;
    const dLng = dLat / Math.max(Math.cos((lat * Math.PI) / 180), 0.01);
    return [[lat - dLat, lng - dLng], [lat + dLat, lng + dLng]];
  }
  const lats = shape.ring.map((p) => p[0]);
  const lngs = shape.ring.map((p) => p[1]);
  return [[Math.min(...lats), Math.min(...lngs)], [Math.max(...lats), Math.max(...lngs)]];
}

/** The list as it will be once a change is saved, so the screen can show it straight away. */
export function applyPatch(list: Suggestion[], id: number, patch: Partial<Suggestion>): Suggestion[] {
  return list.map((s) => (s.id === id ? { ...s, ...patch } : s));
}
