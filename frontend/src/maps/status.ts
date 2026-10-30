import type { components } from "../api/schema";
import type { Media } from "../media/group";

export type MapJob = components["schemas"]["MapJob"];
export type MapLayer = components["schemas"]["MapLayer"];

export const MIN_IMAGES = 5;
export const MIN_GEOTAGGED = 3;

const STAGES: Record<string, string> = {
  preparing: "Getting the photos ready",
  features: "Finding details in each photo",
  matching: "Matching photos to each other",
  reconstructing: "Working out where each photo was taken",
  detecting: "Looking for beds, trees, sheds and more in the photos",
  orthophoto: "Laying the photos onto the ground",
  tiling: "Making map tiles",
  saving: "Saving the map",
};

export const isActive = (job: Pick<MapJob, "status">) => job.status === "queued" || job.status === "running";
export const anyActive = (jobs: MapJob[] | undefined) => !!jobs?.some(isActive);

/** One line saying what a job is doing, or how it ended. */
export function jobSummary(job: MapJob): { label: string; tone: "ok" | "wait" | "bad" } {
  switch (job.status) {
    case "queued":
      return { label: "Waiting for the mapping worker to pick it up", tone: "wait" };
    case "running": {
      const step = STAGES[job.stage ?? ""] ?? "Working";
      return { label: job.cancel_requested ? "Stopping…" : `${step}…`, tone: "wait" };
    }
    case "ready": {
      const parts: string[] = [];
      if (job.detect_objects) parts.push(job.objects_found ? `found ${job.objects_found} ${job.objects_found === 1 ? "object" : "objects"} to review` : "found no objects");
      if (job.overlay) parts.push(job.shots_used != null && job.shots_total != null ? `overlay used ${job.shots_used} of ${job.shots_total} photos` : "overlay built");
      return { label: `Done: ${parts.join("; ") || "finished"}`, tone: "ok" };
    }
    case "cancelled":
      return { label: "Cancelled", tone: "wait" };
    default:
      return { label: job.error ? `Failed: ${job.error}` : "Failed", tone: "bad" };
  }
}

// Mirror the server's defaults (MAPPING_VIDEO_FPS, MAPPING_MAX_FRAMES_PER_VIDEO); the server decides.
export const VIDEO_FPS = 1;
export const MAX_FRAMES_PER_VIDEO = 60;

/** About how many frames a video contributes: one a second, spread over the whole video if that
 *  would exceed the per-video limit. */
export function videoFrames(m: Pick<Media, "duration_s">): number {
  const d = m.duration_s;
  if (!d || d <= 0) return MAX_FRAMES_PER_VIDEO;
  return Math.max(1, Math.min(MAX_FRAMES_PER_VIDEO, Math.ceil(d * Math.min(VIDEO_FPS, MAX_FRAMES_PER_VIDEO / d))));
}

export type Readiness = { ok: boolean; photos: number; videos: number; images: number; located: number; problems: string[]; repeats: { file: Media; of: Media }[] };

/** Mirrors the server's checks so the form can explain a problem before anything is sent.
 *  With no selection it counts every ready photo and video. Only photos can place the map: a video
 *  has a single location, which can't fix position and scale. */
export function readiness(media: Media[], selected: Set<number> | null, maxImages = 150): Readiness {
  const picked = media.filter((m) => m.status === "ready" && (!selected || selected.has(m.id!)));
  const copies = repeatedFiles(picked);
  const chosen = picked.filter((m) => !copies.has(m.id!));
  const photos = chosen.filter((m) => m.kind === "photo");
  const videos = chosen.filter((m) => m.kind === "video");
  const images = photos.length + videos.reduce((n, v) => n + videoFrames(v), 0);
  const located = photos.filter((m) => m.lat != null && m.lng != null).length;
  const problems: string[] = [];
  if (images < MIN_IMAGES) problems.push(`Pick at least ${MIN_IMAGES} photos (or a video long enough for that many frames) that overlap each other (${images} so far).`);
  else if (located < MIN_GEOTAGGED)
    problems.push(`At least ${MIN_GEOTAGGED} photos need a location to place the map (${located} have one). A video can't do this on its own: it only has one location.`);
  if (images > maxImages) problems.push(`That is about ${images} images; pick at most ${maxImages} photos or seconds of video for one map.`);
  return { ok: problems.length === 0, repeats: picked.filter((m) => copies.has(m.id!)).map((m) => ({ file: m, of: copies.get(m.id!)! })), photos: photos.length, videos: videos.length, images, located, problems };
}

/** Camera height suggestion for each way of taking the photos. */
export const defaultHeight = (view: "oblique" | "overhead") => (view === "overhead" ? 10 : 1.7);

/** Clamp an opacity typed or dragged into the 0-1 range the API accepts. */
export const clampOpacity = (value: number) => (Number.isFinite(value) ? Math.min(1, Math.max(0, value)) : 0.85);

export const layersToShow = (layers: MapLayer[] | undefined) => (layers ?? []).filter((l) => l.visible);

/** A map rectangle as Leaflet takes it: [[south, west], [north, east]]. */
export type Box = [[number, number], [number, number]];

export const layerBox = (l: Pick<MapLayer, "bounds">): Box => {
  const [west, south, east, north] = l.bounds ?? [0, 0, 0, 0];
  return [[south, west], [north, east]];
};

/** Where the map should open: everything drawn, every visible photo layer and anything waiting
 *  for review (`extra`), or null if the allotment has none of them (the caller then falls back to the person's location). */
export function initialView(drawn: Box | null | undefined, layers: MapLayer[] | undefined, extra: Box[] = []): Box | null {
  const boxes = [...(drawn ? [drawn] : []), ...layersToShow(layers).map(layerBox), ...extra];
  if (!boxes.length) return null;
  return [
    [Math.min(...boxes.map((b) => b[0][0])), Math.min(...boxes.map((b) => b[0][1]))],
    [Math.max(...boxes.map((b) => b[1][0])), Math.max(...boxes.map((b) => b[1][1]))],
  ];
}

/** Files that look like a second upload of an earlier one (same kind, size, length and shape),
 *  mapped to the earlier one. The server leaves these out of a map, mirroring this rule. */
export function repeatedFiles(media: Media[]): Map<number, Media> {
  const first = new Map<string, Media>();
  const copies = new Map<number, Media>();
  for (const m of [...media].sort((a, b) => a.id! - b.id!)) {
    if (!m.size_bytes) continue;
    const duration = m.duration_s == null ? "" : m.duration_s.toFixed(1);
    const key = [m.kind, m.size_bytes, duration, m.width ?? "", m.height ?? ""].join("|");
    const original = first.get(key);
    if (original) copies.set(m.id!, original);
    else first.set(key, m);
  }
  return copies;
}
