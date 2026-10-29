import { describe, expect, it } from "vitest";
import { applyPatch, confidenceWord, frameSrc, mergeTicks, outlinePoints, photosOf, seenIn, shapeOf, suggestionBox, tickedByDefault, type Suggestion } from "./model";

const s = (id: number, extra: Partial<Suggestion> = {}): Suggestion => ({ id, confidence: 0.7, views: 3, ...extra }) as Suggestion;

describe("confidenceWord", () => {
  it("puts scores into words", () => {
    expect(confidenceWord(0.8)).toBe("likely");
    expect(confidenceWord(0.45)).toBe("possible");
    expect(confidenceWord(0.2)).toBe("unsure");
    expect(confidenceWord(undefined)).toBe("unsure");
  });
});

describe("tickedByDefault", () => {
  it("ticks reasonably sure detections only", () => {
    expect(tickedByDefault(s(1, { confidence: 0.4 }))).toBe(true);
    expect(tickedByDefault(s(1, { confidence: 0.39 }))).toBe(false);
  });
});

describe("seenIn", () => {
  it("is grammatical", () => {
    expect(seenIn({ views: 1 })).toBe("seen in 1 photo");
    expect(seenIn({ views: 4 })).toBe("seen in 4 photos");
  });
});

describe("shapeOf", () => {
  it("turns a point and radius into a circle, swapping to lat/lng", () => {
    expect(shapeOf({ geometry: { type: "Point", coordinates: [-0.12, 51.5] }, radius_m: 0.4 })).toEqual({ type: "circle", centre: [51.5, -0.12], radius: 0.4 });
  });
  it("turns a closed polygon into an open ring in lat/lng order", () => {
    const g = { type: "Polygon", coordinates: [[[0, 1], [2, 1], [2, 3], [0, 3], [0, 1]]] };
    expect(shapeOf({ geometry: g, radius_m: null })).toEqual({ type: "polygon", ring: [[1, 0], [1, 2], [3, 2], [3, 0]] });
  });
  it("copes with nothing usable", () => {
    expect(shapeOf({ geometry: { type: "LineString" }, radius_m: null })).toBeNull();
    expect(shapeOf({ geometry: undefined, radius_m: null })).toBeNull();
  });
});

describe("mergeTicks", () => {
  it("ticks new confident ones, keeps the person's choices for ones already seen", () => {
    const list = [s(1), s(2, { confidence: 0.2 }), s(3), s(4)];
    const kept = mergeTicks(new Set([1]), new Set([1, 3]), list); // person ticked 1, unticked 3; 2 and 4 are new
    expect([...kept].sort()).toEqual([1, 4]);
  });
  it("drops ticks for suggestions that are gone", () => {
    expect([...mergeTicks(new Set([9]), new Set([9]), [s(1)])]).toEqual([1]);
  });
});

describe("suggestionBox", () => {
  it("surrounds a circle by about its radius", () => {
    const [[s0, w0], [n0, e0]] = suggestionBox({ geometry: { type: "Point", coordinates: [-1, 52] }, radius_m: 111 })!;
    expect(n0 - s0).toBeCloseTo(0.002, 4); // 111 m either way, in degrees of latitude
    expect(e0 - w0).toBeGreaterThan(0.002); // degrees of longitude are shorter, so more of them
    expect((s0 + n0) / 2).toBeCloseTo(52, 6);
  });
  it("is the extent of a polygon", () => {
    const g = { type: "Polygon", coordinates: [[[0, 1], [2, 1], [2, 3], [0, 3], [0, 1]]] };
    expect(suggestionBox({ geometry: g, radius_m: null })).toEqual([[1, 0], [3, 2]]);
  });
  it("has none for what it can't draw", () => expect(suggestionBox({ geometry: { type: "LineString" }, radius_m: null })).toBeNull());
});

describe("photos of a suggestion", () => {
  const sighting = (id: number, outline: number[][] = [[0, 0], [1, 0], [1, 1]]) => ({ media_id: id, outline, score: 0.8, url: `/u${id}` });

  it("shows the first few and counts the rest", () => {
    const s = { sightings: [1, 2, 3, 4, 5].map((i) => sighting(i)) };
    const { shown, more } = photosOf(s);
    expect(shown.map((x) => x.media_id)).toEqual([1, 2, 3]);
    expect(more).toBe(2);
  });

  it("copes with no photos, as for suggestions made before they were kept", () => {
    expect(photosOf({})).toEqual({ shown: [], more: 0 });
    expect(photosOf({ sightings: [] })).toEqual({ shown: [], more: 0 });
  });

  it("ignores a sighting with no usable outline", () => {
    expect(photosOf({ sightings: [sighting(1, [[0, 0]]), sighting(2)] }).shown.map((x) => x.media_id)).toEqual([2]);
  });

  it("writes an outline as SVG points", () => {
    expect(outlinePoints([[0.25, 0.5], [0.75, 0.5], [0.5, 1]])).toBe("0.25,0.5 0.75,0.5 0.5,1");
    expect(outlinePoints(undefined)).toBe("");
  });
});

describe("applyPatch", () => {
  it("changes only the one suggestion and leaves the list as it was", () => {
    const list = [s(1, { name: "Shed" }), s(2, { name: "Tree" })];
    const out = applyPatch(list, 2, { name: "Elm" });
    expect(out.map((x) => x.name)).toEqual(["Shed", "Elm"]);
    expect(out[0]).toBe(list[0]);
    expect(list[1].name).toBe("Tree");
  });
});

describe("sightings in videos", () => {
  const shot = (extra: object) => ({ media_id: 1, outline: [[0, 0], [1, 0], [1, 1]], score: 0.8, url: "/v.mp4?t=tok", ...extra });

  it("opens the video at the second the object was seen", () => {
    expect(frameSrc(shot({ kind: "video", at_s: 12.5 }))).toBe("/v.mp4?t=tok#t=12.5");
    expect(frameSrc(shot({ kind: "photo" }))).toBeUndefined();
  });

  it("leaves out a video sighting saved without its second, rather than show the wrong frame", () => {
    const { shown } = photosOf({ sightings: [shot({ kind: "video" }), shot({ kind: "photo", media_id: 2 })] });
    expect(shown.map((x) => x.media_id)).toEqual([2]);
  });
});

describe("video sightings with a saved still", () => {
  it("are kept even without the second", () => {
    const x = { media_id: 3, kind: "video", outline: [[0, 0], [1, 0], [1, 1]], score: 0.8, url: "/v", still_url: "/still" };
    expect(photosOf({ sightings: [x] }).shown).toHaveLength(1);
  });
});
