import { areaLabel, centreOf, colourOf, frameFor, GROWING, PALETTE, ringOf, statusRequest, type LonLat } from "./geometry";

const LAT = 51;
const DLAT = 1 / 111_320;
const DLON = 1 / (111_320 * Math.cos((LAT * Math.PI) / 180));
const ring: LonLat[] = [
  [-1, LAT],
  [-1 + 4 * DLON, LAT],
  [-1 + 4 * DLON, LAT + 1.2 * DLAT],
  [-1, LAT + 1.2 * DLAT],
];

test("the frame fits the bed with north at the top and true proportions", () => {
  const f = frameFor(ring, 300, 200);
  const sw = f.project(ring[0]);
  const se = f.project(ring[1]);
  const nw = f.project(ring[3]);
  expect(nw[1]).toBeLessThan(sw[1]);
  expect((se[0] - sw[0]) / (sw[1] - nw[1])).toBeCloseTo(4 / 1.2, 1);
  expect(Math.min(sw[0], se[0])).toBeGreaterThanOrEqual(0);
  expect(Math.max(sw[0], se[0])).toBeLessThanOrEqual(300);
});

test("polygons lose their closing point; nothing gives nothing", () => {
  expect(ringOf({ coordinates: [[...ring, ring[0]]] })).toEqual(ring);
  expect(ringOf(null)).toEqual([]);
  expect(centreOf(ring)[0]).toBeCloseTo(-1 + 2 * DLON, 9);
});

test("wording, colours and the queued status change", () => {
  expect(areaLabel(2.44)).toBe("2.4 m²");
  expect(areaLabel(48.2)).toBe("48 m²");
  expect(colourOf(3)).toBe(PALETTE[3]);
  expect(colourOf(null)).toBe(PALETTE[7]);
  expect(GROWING).toEqual(["sown", "growing", "harvesting"]);
  expect(statusRequest(1, 9, "growing")).toEqual({ method: "PATCH", path: "/api/v1/allotments/1/plantings/9", body: { status: "growing" } });
});
