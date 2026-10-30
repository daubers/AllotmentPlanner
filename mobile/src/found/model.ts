import type { components } from "../api/schema";

export type Suggestion = components["schemas"]["Suggestion"];
export type Sighting = components["schemas"]["Sighting"];

export const KINDS = ["bed", "path", "shed", "tree", "water", "compost", "boundary", "other"] as const;
export type Kind = (typeof KINDS)[number];

/** Photos the phone can draw: a picture with a usable outline. A video frame only counts once the
 *  server has kept a still of it (the phone can't hold a video at one second like a browser). */
export function photosOf(s: Pick<Suggestion, "sightings">): Sighting[] {
  return (s.sightings ?? []).filter((x) => (x.outline?.length ?? 0) >= 3 && (x.kind !== "video" || !!x.still_url));
}

/** Which link to draw for a sighting: the saved still, else the photo (full size or the thumbnail). */
export function pictureOf(x: Sighting, full: boolean): string | undefined {
  return x.still_url ?? (full ? x.url : (x.thumb_url ?? x.url)) ?? undefined;
}

/** An outline as the `points` of an SVG polygon in a 0..1 box (the photo is stretched to that box). */
export function outlinePoints(outline: number[][] | undefined): string {
  return (outline ?? []).map(([x, y]) => `${x},${y}`).join(" ");
}

export function confidenceWord(c: number | undefined): "likely" | "possible" | "unsure" {
  const v = c ?? 0;
  return v >= 0.6 ? "likely" : v >= 0.4 ? "possible" : "unsure";
}

export const isLikely = (s: Pick<Suggestion, "confidence">): boolean => (s.confidence ?? 0) >= 0.4;

export function seenIn(s: Pick<Suggestion, "views">): string {
  const n = s.views ?? 1;
  return n === 1 ? "seen in 1 photo" : `seen in ${n} photos`;
}

/** The list with a change shown straight away, ahead of the server confirming it. */
export function applyPatch(list: Suggestion[], id: number, patch: Partial<Suggestion>): Suggestion[] {
  return list.map((s) => (s.id === id ? { ...s, ...patch } : s));
}
