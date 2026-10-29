import { LayerGroup, LayersControl, Polygon, Tooltip } from "react-leaflet";
import { colourOf, ringOf } from "../plantings/geometry";
import { usePlantings } from "../plantings/hooks";

/** What is growing in the beds, as labelled regions you can switch on and off with the layer control. */
export default function PlantingShapes({ allotmentId }: { allotmentId: number }) {
  const plantings = usePlantings(allotmentId, { growing: true });
  return (
    <LayersControl.Overlay checked name="Plantings">
      <LayerGroup>
        {(plantings.data ?? []).map((p) => {
          const ring = ringOf(p.region);
          if (ring.length < 3) return null;
          const colour = colourOf(p.packet_id);
          return (
            <Polygon
              key={p.id}
              positions={ring.map(([lon, lat]) => [lat, lon] as [number, number])}
              pathOptions={{ color: colour, weight: 2, fillColor: colour, fillOpacity: 0.45 }}
            >
              <Tooltip direction="center" permanent className="planting-label">{p.packet_name ?? "Planting"}</Tooltip>
            </Polygon>
          );
        })}
      </LayerGroup>
    </LayersControl.Overlay>
  );
}
