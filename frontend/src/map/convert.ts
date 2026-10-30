import L from "leaflet";

import { colourFor, KINDS, KIND_COLOURS, type Kind } from "./kinds";

export { colourFor, KINDS, KIND_COLOURS };
export type { Kind };

export type FeatureProps = { name: string; kind: Kind; radius_m: number | null; style: Record<string, unknown>; locked: boolean; z: number };
export type GeoJSONFeature = {
  type: "Feature";
  id?: number;
  geometry: { type: string; coordinates: unknown };
  properties: Partial<FeatureProps>;
};

export function styleFor(kind: string | undefined): L.PathOptions {
  const color = colourFor(kind);
  return { color, fillColor: color, fillOpacity: 0.3, weight: 2 };
}

/** Leaflet layer drawn in the editor -> GeoJSON geometry (+ radius for circles). */
export function layerToGeometry(layer: L.Layer): { geometry: GeoJSONFeature["geometry"]; radius_m: number | null } {
  const geometry = (layer as L.Layer & { toGeoJSON(): GeoJSON.Feature }).toGeoJSON().geometry as GeoJSONFeature["geometry"];
  const radius_m = layer instanceof L.Circle ? layer.getRadius() : null;
  return { geometry, radius_m };
}

/** GeoJSON feature from the API -> Leaflet layer (circles are Point + radius_m). */
export function featureToLayer(feature: GeoJSONFeature): L.Layer {
  const { geometry, properties } = feature;
  // A locked layer is invisible to Geoman, so no drag, edit or delete mode can touch it.
  const locked = properties.locked ? { pmIgnore: true, className: "locked" } : {};
  const style = { ...styleFor(properties.kind), ...locked };
  switch (geometry.type) {
    case "Point": {
      const latlng = L.GeoJSON.coordsToLatLng(geometry.coordinates as [number, number]);
      return properties.radius_m ? L.circle(latlng, { ...style, radius: properties.radius_m }) : L.marker(latlng, locked);
    }
    case "LineString":
      return L.polyline(L.GeoJSON.coordsToLatLngs(geometry.coordinates as number[][], 0), style);
    case "Polygon":
      return L.polygon(L.GeoJSON.coordsToLatLngs(geometry.coordinates as number[][][], 1), style);
    default:
      throw new Error(`Unsupported geometry type: ${geometry.type}`);
  }
}

export function restyle(layer: L.Layer, kind: string): void {
  if ("setStyle" in layer) (layer as L.Path).setStyle(styleFor(kind));
}
