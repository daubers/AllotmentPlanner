import L from "leaflet";
import { describe, expect, it } from "vitest";
import { featureToLayer, layerToGeometry, styleFor } from "./convert";

describe("map conversion", () => {
  it("round-trips a polygon", () => {
    const geometry = { type: "Polygon", coordinates: [[[-1, 51], [-1, 51.001], [-0.999, 51.001], [-1, 51]]] };
    const layer = featureToLayer({ type: "Feature", id: 1, geometry, properties: { kind: "bed" } });
    expect(layer).toBeInstanceOf(L.Polygon);
    const out = layerToGeometry(layer);
    expect(out.geometry.type).toBe("Polygon");
    expect(out.radius_m).toBeNull();
    expect((out.geometry.coordinates as number[][][])[0][0]).toEqual([-1, 51]);
  });

  it("treats a Point with radius_m as a circle and reads the radius back", () => {
    const layer = featureToLayer({
      type: "Feature",
      geometry: { type: "Point", coordinates: [-1, 51] },
      properties: { radius_m: 2.5, kind: "tree" },
    });
    expect(layer).toBeInstanceOf(L.Circle);
    const out = layerToGeometry(layer);
    expect(out.radius_m).toBe(2.5);
    expect(out.geometry).toEqual({ type: "Point", coordinates: [-1, 51] });
  });

  it("treats a plain Point as a marker and a LineString as a polyline", () => {
    const point = featureToLayer({ type: "Feature", geometry: { type: "Point", coordinates: [0, 0] }, properties: {} });
    expect(point).toBeInstanceOf(L.Marker);
    const line = featureToLayer({ type: "Feature", geometry: { type: "LineString", coordinates: [[0, 0], [1, 1]] }, properties: { kind: "path" } });
    expect(line).toBeInstanceOf(L.Polyline);
    expect(layerToGeometry(line).geometry.type).toBe("LineString");
  });

  it("rejects unsupported geometry and falls back to a default style", () => {
    expect(() => featureToLayer({ type: "Feature", geometry: { type: "MultiPoint", coordinates: [] }, properties: {} })).toThrow();
    expect(styleFor("nonsense").color).toBe(styleFor("other").color);
  });
});

describe("locked features", () => {
  it("are hidden from Geoman so nothing can drag or edit them", () => {
    const geometry = { type: "Polygon", coordinates: [[[-1, 51], [-1, 51.001], [-0.999, 51.001], [-1, 51]]] };
    const free = featureToLayer({ type: "Feature", id: 1, geometry, properties: { kind: "bed" } });
    const locked = featureToLayer({ type: "Feature", id: 1, geometry, properties: { kind: "bed", locked: true } });
    expect((free as L.Path).options.pmIgnore).toBeUndefined();
    expect((locked as L.Path).options.pmIgnore).toBe(true);
    const pin = featureToLayer({ type: "Feature", id: 2, geometry: { type: "Point", coordinates: [-1, 51] }, properties: { locked: true } });
    expect((pin as L.Marker).options.pmIgnore).toBe(true);
  });
});
