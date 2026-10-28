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

/** Mirrors the server's checks so the form can explain a problem before anything is sent. */
export function readiness(media: Media[], selected: Set<number> | null, maxImages = 150): { ok: boolean; total: number; located: number; problems: string[] } {
  const chosen = media.filter((m) => m.status === "ready" && (selected ? selected.has(m.id!) : m.kind === "photo"));
  const located = chosen.filter((m) => m.lat != null && m.lng != null).length;
  const problems: string[] = [];
  if (chosen.length < MIN_IMAGES) problems.push(`Pick at least ${MIN_IMAGES} photos that overlap each other (${chosen.length} so far).`);
  else if (located < MIN_GEOTAGGED) problems.push(`At least ${MIN_GEOTAGGED} need a location to place the map (${located} have one).`);
  if (chosen.length > maxImages) problems.push(`Pick at most ${maxImages} for one map.`);
  return { ok: problems.length === 0, total: chosen.length, located, problems };
}

/** Camera height suggestion for each way of taking the photos. */
export const defaultHeight = (view: "oblique" | "overhead") => (view === "overhead" ? 10 : 1.7);

/** Clamp an opacity typed or dragged into the 0-1 range the API accepts. */
export const clampOpacity = (value: number) => (Number.isFinite(value) ? Math.min(1, Math.max(0, value)) : 0.85);

export const layersToShow = (layers: MapLayer[] | undefined) => (layers ?? []).filter((l) => l.visible);
