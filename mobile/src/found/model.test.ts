import { applyPatch, confidenceWord, isLikely, outlinePoints, pictureOf, photosOf, seenIn, type Sighting } from "./model";

const tri = [[0.1, 0.1], [0.5, 0.1], [0.3, 0.6]];
const sighting = (extra: Partial<Sighting> = {}): Sighting => ({ media_id: 1, outline: tri, kind: "photo", url: "/full", thumb_url: "/thumb", ...extra });

describe("photosOf", () => {
  it("keeps photos with a real outline, in the order given", () => {
    const a = sighting({ media_id: 1 });
    const b = sighting({ media_id: 2 });
    expect(photosOf({ sightings: [a, b] })).toEqual([a, b]);
  });

  it("drops outlines too small to draw", () => {
    expect(photosOf({ sightings: [sighting({ outline: [[0, 0], [1, 1]] }), sighting({ outline: undefined })] })).toEqual([]);
  });

  it("keeps a video frame only when a still was saved", () => {
    const video = sighting({ kind: "video", at_s: 4 });
    expect(photosOf({ sightings: [video] })).toEqual([]);
    expect(photosOf({ sightings: [{ ...video, still_url: "/still" }] })).toHaveLength(1);
  });

  it("copes with no sightings at all", () => {
    expect(photosOf({})).toEqual([]);
  });
});

describe("pictureOf", () => {
  it("prefers a still, then the full photo or its thumbnail", () => {
    expect(pictureOf(sighting({ still_url: "/still" }), false)).toBe("/still");
    expect(pictureOf(sighting(), true)).toBe("/full");
    expect(pictureOf(sighting(), false)).toBe("/thumb");
    expect(pictureOf(sighting({ thumb_url: null }), false)).toBe("/full");
  });
});

test("outlinePoints writes SVG points", () => {
  expect(outlinePoints(tri)).toBe("0.1,0.1 0.5,0.1 0.3,0.6");
  expect(outlinePoints(undefined)).toBe("");
});

test("confidence in words", () => {
  expect([0.9, 0.5, 0.1, undefined].map(confidenceWord)).toEqual(["likely", "possible", "unsure", "unsure"]);
  expect(isLikely({ confidence: 0.4 })).toBe(true);
  expect(isLikely({ confidence: 0.39 })).toBe(false);
});

test("seenIn pluralises", () => {
  expect(seenIn({ views: 1 })).toBe("seen in 1 photo");
  expect(seenIn({ views: 3 })).toBe("seen in 3 photos");
});

test("applyPatch changes only the one suggestion", () => {
  const list = [{ id: 1, name: "a" }, { id: 2, name: "b" }];
  expect(applyPatch(list, 2, { name: "c" })).toEqual([{ id: 1, name: "a" }, { id: 2, name: "c" }]);
});
