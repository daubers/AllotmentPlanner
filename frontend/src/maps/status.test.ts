import { describe, expect, it } from "vitest";
import type { Media } from "../media/group";
import { anyActive, clampOpacity, defaultHeight, jobSummary, layersToShow, readiness, type MapJob, type MapLayer } from "./status";

const job = (extra: Partial<MapJob>): MapJob => ({ id: 1, status: "queued", stage: "", ...extra }) as MapJob;
const photo = (id: number, extra: Partial<Media> = {}): Media => ({ id, kind: "photo", status: "ready", lat: 51.5, lng: -0.12, ...extra }) as Media;

describe("jobSummary", () => {
  it("explains a queued job so a missing worker is obvious", () => expect(jobSummary(job({})).label).toMatch(/Waiting for the mapping worker/));
  it("names the running stage", () => {
    expect(jobSummary(job({ status: "running", stage: "matching" }))).toEqual({ label: "Matching photos to each other…", tone: "wait" });
    expect(jobSummary(job({ status: "running", stage: "mystery" })).label).toBe("Working…");
  });
  it("shows a cancel in progress", () => expect(jobSummary(job({ status: "running", stage: "tiling", cancel_requested: true })).label).toBe("Stopping…"));
  it("reports how many photos made it into the map", () => {
    expect(jobSummary(job({ status: "ready", shots_used: 22, shots_total: 25 }))).toEqual({ label: "Done: used 22 of 25 photos", tone: "ok" });
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

describe("readiness", () => {
  const many = (n: number, extra: Partial<Media> = {}) => Array.from({ length: n }, (_, i) => photo(i + 1, extra));
  it("is ok with enough located, ready photos", () => expect(readiness(many(6), null)).toMatchObject({ ok: true, total: 6, located: 6 }));
  it("asks for more photos", () => expect(readiness(many(4), null).problems[0]).toMatch(/at least 5/));
  it("asks for locations", () => {
    const r = readiness([...many(2), ...many(5, { lat: null, lng: null }).map((m, i) => ({ ...m, id: 100 + i }))], null);
    expect(r.ok).toBe(false);
    expect(r.problems[0]).toMatch(/3 need a location.*2 have one/);
  });
  it("ignores photos still processing and videos in the default selection", () => {
    expect(readiness([...many(5), photo(50, { status: "pending" }), photo(51, { kind: "video" })], null).total).toBe(5);
  });
  it("respects an explicit selection", () => {
    expect(readiness(many(8), new Set([1, 2, 3])).total).toBe(3);
  });
  it("enforces the upper limit", () => expect(readiness(many(8), null, 6).problems.join(" ")).toMatch(/at most 6/));
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
