import L from "leaflet";

export type Kind = "bed" | "path" | "shed" | "tree" | "water" | "compost" | "boundary" | "other";
export const KINDS: Kind[] = ["bed", "path", "shed", "tree", "water", "compost", "boundary", "other"];

export type FeatureProps = { name: string; kind: Kind; radius_m: number | null; style: Record<string, unknown> };
export type GeoJSONFeature = {
  type: "Feature";
  id?: number;
  geometry: { type: string; coordinates: unknown };
  properties: Partial<FeatureProps>;
};

export const KIND_COLOURS: Record<Kind, string> = {
  bed: "#3f8f3f",
  path: "#a08c6a",
  shed: "#8a5a3c",
  tree: "#1f6b3a",
  water: "#2f7fc1",
  compost: "#6b4f2a",
  boundary: "#444444",
  other: "#7a5ea8",
};

export function styleFor(kind: string | undefined): L.PathOptions {
  const color = KIND_COLOURS[(kind as Kind) ?? "other"] ?? KIND_COLOURS.other;
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
  const style = styleFor(properties.kind);
  switch (geometry.type) {
    case "Point": {
      const latlng = L.GeoJSON.coordsToLatLng(geometry.coordinates as [number, number]);
      return properties.radius_m ? L.circle(latlng, { ...style, radius: properties.radius_m }) : L.marker(latlng);
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
