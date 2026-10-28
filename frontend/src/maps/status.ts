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
    case "ready":
      return {
        label: job.shots_used != null && job.shots_total != null ? `Done: used ${job.shots_used} of ${job.shots_total} photos` : "Done",
        tone: "ok",
      };
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

export type Readiness = { ok: boolean; photos: number; videos: number; images: number; located: number; problems: string[] };

/** Mirrors the server's checks so the form can explain a problem before anything is sent.
 *  With no selection it counts every ready photo and video. Only photos can place the map: a video
 *  has a single location, which can't fix position and scale. */
export function readiness(media: Media[], selected: Set<number> | null, maxImages = 150): Readiness {
  const chosen = media.filter((m) => m.status === "ready" && (!selected || selected.has(m.id!)));
  const photos = chosen.filter((m) => m.kind === "photo");
  const videos = chosen.filter((m) => m.kind === "video");
  const images = photos.length + videos.reduce((n, v) => n + videoFrames(v), 0);
  const located = photos.filter((m) => m.lat != null && m.lng != null).length;
  const problems: string[] = [];
  if (images < MIN_IMAGES) problems.push(`Pick at least ${MIN_IMAGES} photos (or a video long enough for that many frames) that overlap each other (${images} so far).`);
  else if (located < MIN_GEOTAGGED)
    problems.push(`At least ${MIN_GEOTAGGED} photos need a location to place the map (${located} have one). A video can't do this on its own: it only has one location.`);
  if (images > maxImages) problems.push(`That is about ${images} images; pick at most ${maxImages} photos or seconds of video for one map.`);
  return { ok: problems.length === 0, photos: photos.length, videos: videos.length, images, located, problems };
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

/** Where the map should open: everything drawn plus every visible photo layer, or null if the
 *  allotment has neither (the caller then falls back to the person's location). */
export function initialView(drawn: Box | null | undefined, layers: MapLayer[] | undefined): Box | null {
  const boxes = [...(drawn ? [drawn] : []), ...layersToShow(layers).map(layerBox)];
  if (!boxes.length) return null;
  return [
    [Math.min(...boxes.map((b) => b[0][0])), Math.min(...boxes.map((b) => b[0][1]))],
    [Math.max(...boxes.map((b) => b[1][0])), Math.max(...boxes.map((b) => b[1][1]))],
  ];
}
