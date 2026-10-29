import { describe, expect, it } from "vitest";
import { areaLabel, areaM2, colourOf, distanceToEdgeM, frameFor, pointInRing, polygonOf, ringOf, withinBed, type LonLat } from "./geometry";

const LAT = 51;
const DLAT = 1 / 111_320;
const DLON = 1 / (111_320 * Math.cos((LAT * Math.PI) / 180));
const rect = (w: number, h: number): LonLat[] => [
  [-1, LAT],
  [-1 + w * DLON, LAT],
  [-1 + w * DLON, LAT + h * DLAT],
  [-1, LAT + h * DLAT],
];
const BED = rect(4, 1.2);

describe("frame", () => {
  it("fits the bed and round-trips points", () => {
    const f = frameFor(BED);
    const [x, y] = f.project([-1 + 2 * DLON, LAT + 0.6 * DLAT]);
    expect(x).toBeGreaterThan(0);
    expect(x).toBeLessThan(f.width);
    const [lon, lat] = f.unproject([x, y]);
    expect(lon).toBeCloseTo(-1 + 2 * DLON, 9);
    expect(lat).toBeCloseTo(LAT + 0.6 * DLAT, 9);
  });
  it("puts north at the top and keeps the shape's proportions", () => {
    const f = frameFor(BED);
    const sw = f.project(BED[0]);
    const nw = f.project(BED[3]);
    const se = f.project(BED[1]);
    expect(nw[1]).toBeLessThan(sw[1]);
    expect((se[0] - sw[0]) / (sw[1] - nw[1])).toBeCloseTo(4 / 1.2, 1);
  });
});

describe("shapes", () => {
  it("measures area in square metres", () => {
    expect(areaM2(BED)).toBeCloseTo(4.8, 1);
    expect(areaM2(BED.slice(0, 2))).toBe(0);
  });
  it("knows what is inside, and what is near enough to the edge", () => {
    expect(pointInRing([-1 + 2 * DLON, LAT + 0.6 * DLAT], BED)).toBe(true);
    expect(pointInRing([-1 + 5 * DLON, LAT + 0.6 * DLAT], BED)).toBe(false);
    expect(withinBed([-1 + 4.1 * DLON, LAT + 0.6 * DLAT], BED)).toBe(true); // 10 cm over
    expect(withinBed([-1 + 4.6 * DLON, LAT + 0.6 * DLAT], BED)).toBe(false); // 60 cm over
    expect(distanceToEdgeM([-1 + 2 * DLON, LAT + 0.5 * DLAT], BED)).toBeCloseTo(0.5, 1);
  });
  it("converts to and from GeoJSON polygons", () => {
    const poly = polygonOf(BED);
    expect(poly.coordinates[0]).toHaveLength(5);
    expect(ringOf(poly)).toEqual(BED);
    expect(ringOf(null)).toEqual([]);
  });
  it("labels areas and colours packets consistently", () => {
    expect(areaLabel(2.44)).toBe("2.4 m²");
    expect(areaLabel(48.2)).toBe("48 m²");
    expect(colourOf(3)).toBe(colourOf(3 + 8));
    expect(colourOf(null)).toBe(colourOf(undefined));
  });
});
