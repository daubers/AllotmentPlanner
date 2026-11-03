import { extentPoints, shapesOf } from "./shapes";

const poly = (...c: [number, number][]) => ({ type: "Polygon", coordinates: [[...c, c[0]]] });

describe("shapesOf", () => {
  it("reads areas, lines, points and circles, and skips what it cannot draw", () => {
    const shapes = shapesOf([
      { id: 1, geometry: poly([0, 0], [1, 0], [1, 1]), properties: { kind: "bed", name: "Bed A" } },
      { id: 2, geometry: { type: "LineString", coordinates: [[0, 0], [1, 1]] }, properties: { kind: "path" } },
      { id: 3, geometry: { type: "Point", coordinates: [0.5, 0.5] }, properties: { kind: "tree", radius_m: 2 } },
      { id: 4, geometry: { type: "Point", coordinates: [0.5, 0.5] }, properties: { kind: "water" } },
      { id: 5, geometry: poly([0, 0], [1, 0]), properties: {} },
      { id: 6, geometry: null, properties: {} },
    ]);
    expect(shapes.map((s) => [s.id, s.type, s.kind, s.radiusM])).toEqual([
      [1, "area", "bed", null],
      [2, "line", "path", null],
      [3, "point", "tree", 2],
      [4, "point", "water", null],
    ]);
    expect(shapes[0].points).toHaveLength(3); // closing point dropped
    expect(shapes[0].name).toBe("Bed A");
  });

  it("copes with nothing", () => {
    expect(shapesOf(undefined)).toEqual([]);
    expect(shapesOf([])).toEqual([]);
  });

  it("widens the extent for a circle", () => {
    const shapes = shapesOf([{ id: 1, geometry: { type: "Point", coordinates: [0, 51] }, properties: { radius_m: 10, kind: "tree" } }]);
    const pts = extentPoints(shapes);
    expect(pts.length).toBe(3);
    expect(pts[2][1] - pts[1][1]).toBeCloseTo(20 / 111_320, 8);
  });
});
