import { describe, expect, it } from "vitest";
import type { Media } from "../media/group";
import { anyActive, clampOpacity, defaultHeight, initialView, jobSummary, layerBox, layersToShow, readiness, videoFrames, type MapJob, type MapLayer } from "./status";

const job = (extra: Partial<MapJob>): MapJob => ({ id: 1, status: "queued", stage: "", ...extra }) as MapJob;
const photo = (id: number, extra: Partial<Media> = {}): Media => ({ id, kind: "photo", status: "ready", lat: 51.5, lng: -0.12, ...extra }) as Media;

describe("jobSummary", () => {
  it("explains a queued job so a missing worker is obvious", () => expect(jobSummary(job({})).label).toMatch(/Waiting for the mapping worker/));
  it("names the running stage", () => {
    expect(jobSummary(job({ status: "running", stage: "matching" }))).toEqual({ label: "Matching photos to each other…", tone: "wait" });
    expect(jobSummary(job({ status: "running", stage: "mystery" })).label).toBe("Working…");
  });
  it("shows a cancel in progress", () => expect(jobSummary(job({ status: "running", stage: "tiling", cancel_requested: true })).label).toBe("Stopping…"));
  it("reports what a finished job produced", () => {
    expect(jobSummary(job({ status: "ready", detect_objects: true, objects_found: 7, overlay: false }))).toEqual({ label: "Done: found 7 objects to review", tone: "ok" });
    expect(jobSummary(job({ status: "ready", detect_objects: true, objects_found: 1 })).label).toBe("Done: found 1 object to review");
    expect(jobSummary(job({ status: "ready", detect_objects: true, objects_found: 0 })).label).toBe("Done: found no objects");
    expect(jobSummary(job({ status: "ready", detect_objects: false, overlay: true, shots_used: 22, shots_total: 25 })).label).toBe("Done: overlay used 22 of 25 photos");
    expect(jobSummary(job({ status: "ready", detect_objects: true, objects_found: 3, overlay: true, shots_used: 5, shots_total: 9 })).label).toBe("Done: found 3 objects to review; overlay used 5 of 9 photos");
  });
  it("names the recognition stage", () => {
    expect(jobSummary(job({ status: "running", stage: "detecting" })).label).toBe("Looking for beds, trees, sheds and more in the photos…");
  });
  it("shows the failure reason", () => {
    expect(jobSummary(job({ status: "failed", error: "Only 2 of the images have a location" }))).toEqual({
      label: "Failed: Only 2 of the images have a location",
      tone: "bad",
    });
    expect(jobSummary(job({ status: "cancelled" })).label).toBe("Cancelled");
  });
});

describe("anyActive", () => {
  it("is true while something is queued or running", () => {
    expect(anyActive([job({ status: "ready" }), job({ status: "running" })])).toBe(true);
    expect(anyActive([job({ status: "failed" })])).toBe(false);
    expect(anyActive(undefined)).toBe(false);
  });
});

describe("videoFrames", () => {
  it("is about one frame a second", () => expect(videoFrames({ duration_s: 4 })).toBe(4));
  it("spreads long videos over their whole length, capped at the limit", () => {
    expect(videoFrames({ duration_s: 120 })).toBe(60);
    expect(videoFrames({ duration_s: 600 })).toBe(60);
  });
  it("assumes the maximum when the length is unknown, and at least one frame otherwise", () => {
    expect(videoFrames({ duration_s: null })).toBe(60);
    expect(videoFrames({ duration_s: 0.2 })).toBe(1);
  });
});

describe("readiness", () => {
  const many = (n: number, extra: Partial<Media> = {}) => Array.from({ length: n }, (_, i) => photo(i + 1, extra));
  const video = (id: number, seconds: number, extra: Partial<Media> = {}) =>
    ({ id, kind: "video", status: "ready", duration_s: seconds, lat: 51.5, lng: -0.12, ...extra }) as Media;
  it("is ok with enough located, ready photos", () => expect(readiness(many(6), null)).toMatchObject({ ok: true, photos: 6, images: 6, located: 6 }));
  it("asks for more photos", () => expect(readiness(many(4), null).problems[0]).toMatch(/at least 5/));
  it("asks for locations", () => {
    const r = readiness([...many(2), ...many(5, { lat: null, lng: null }).map((m, i) => ({ ...m, id: 100 + i }))], null);
    expect(r.ok).toBe(false);
    expect(r.problems[0]).toMatch(/3 photos need a location.*2 have one/);
  });
  it("ignores media still processing", () => {
    expect(readiness([...many(5), photo(50, { status: "pending" }), video(51, 30, { status: "pending" })], null).images).toBe(5);
  });
  it("counts a video as the frames taken from it", () => {
    const r = readiness([...many(3), video(10, 8)], null);
    expect(r).toMatchObject({ ok: true, photos: 3, videos: 1, images: 11, located: 3 });
  });
  it("lets a video make up the numbers but not place the map", () => {
    expect(readiness([...many(2), video(10, 30)], null).problems.join(" ")).toMatch(/3 photos need a location.*\(2 have one\)/);
    const alone = readiness([video(10, 120)], null);
    expect(alone.ok).toBe(false);
    expect(alone.problems[0]).toMatch(/only has one location/);
  });
  it("does not let a located video count as a located photo", () => {
    expect(readiness([...many(2), video(10, 30, { lat: 51.5, lng: -0.12 })], null).located).toBe(2);
  });
  it("respects an explicit selection", () => {
    expect(readiness([...many(8), video(20, 10)], new Set([1, 2, 3])).images).toBe(3);
  });
  it("enforces the upper limit using frame counts", () => {
    expect(readiness([...many(3), video(10, 600), video(11, 600)], null, 100).problems.join(" ")).toMatch(/about 123 images.*at most 100/);
  });
});

describe("small helpers", () => {
  it("suggests a height for the way the photos were taken", () => {
    expect(defaultHeight("oblique")).toBe(1.7);
    expect(defaultHeight("overhead")).toBe(10);
  });
  it("keeps opacity in range", () => {
    expect(clampOpacity(1.4)).toBe(1);
    expect(clampOpacity(-1)).toBe(0);
    expect(clampOpacity(Number.NaN)).toBe(0.85);
  });
  it("only shows visible layers", () => {
    const layers = [{ id: 1, visible: true }, { id: 2, visible: false }] as MapLayer[];
    expect(layersToShow(layers).map((l) => l.id)).toEqual([1]);
    expect(layersToShow(undefined)).toEqual([]);
  });
});

describe("initialView", () => {
  const layer = (id: number, bounds: number[], visible = true) => ({ id, visible, bounds }) as MapLayer; // [w, s, e, n]
  it("is null when there is nothing to show", () => {
    expect(initialView(null, [])).toBeNull();
    expect(initialView(undefined, undefined)).toBeNull();
  });
  it("opens on a photo layer when nothing has been drawn", () => {
    expect(initialView(null, [layer(1, [-1.501, 52.0, -1.499, 52.001])])).toEqual([[52.0, -1.501], [52.001, -1.499]]);
  });
  it("covers both the drawn shapes and the layers", () => {
    const drawn: [[number, number], [number, number]] = [[51.0, -0.2], [51.1, -0.1]];
    expect(initialView(drawn, [layer(1, [-0.15, 50.9, 0.0, 51.05])])).toEqual([[50.9, -0.2], [51.1, 0.0]]);
  });
  it("ignores hidden layers", () => {
    expect(initialView(null, [layer(1, [0, 0, 1, 1], false)])).toBeNull();
    expect(initialView([[1, 1], [2, 2]], [layer(1, [50, 50, 51, 51], false)])).toEqual([[1, 1], [2, 2]]);
  });
  it("includes suggestions waiting for review, even with nothing else", () => {
    expect(initialView(null, [], [[[1, 1], [2, 2]]])).toEqual([[1, 1], [2, 2]]);
    expect(initialView([[0, 0], [1, 1]], [], [[[5, 5], [6, 6]]])).toEqual([[0, 0], [6, 6]]);
  });
  it("converts a layer's [west, south, east, north] to a Leaflet box", () => {
    expect(layerBox({ bounds: [-1, 2, 3, 4] })).toEqual([[2, -1], [4, 3]]);
  });
});
