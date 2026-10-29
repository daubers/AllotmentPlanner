import React from "react";
import Svg, { Polygon, Text as SvgText } from "react-native-svg";
import { usePalette } from "../ui/theme";
import { centreOf, colourOf, frameFor, type LonLat } from "./geometry";

export type Region = { id: number; label: string; ring: LonLat[]; packetId?: number | null; selected?: boolean };

/** The bed with what is growing in it, as labelled regions. A picture only: planting areas are drawn on the web. */
export default function BedSketch({ ring, regions, width = 320, height = 200 }: { ring: LonLat[]; regions: Region[]; width?: number; height?: number }) {
  const p = usePalette();
  const frame = frameFor(ring, width, height);
  const pts = (r: LonLat[]) => r.map((c) => frame.project(c).map((n) => n.toFixed(1)).join(",")).join(" ");
  return (
    <Svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} accessibilityLabel="Sketch of the bed">
      <Polygon points={pts(ring)} fill={p.surfaceAlt} stroke={p.border} strokeWidth={2} />
      {regions.map((r) => (
        <React.Fragment key={r.id}>
          <Polygon points={pts(r.ring)} fill={colourOf(r.packetId)} fillOpacity={0.55} stroke={colourOf(r.packetId)} strokeWidth={r.selected ? 3 : 1.5} />
          {r.ring.length > 0 && (
            <SvgText x={frame.project(centreOf(r.ring))[0]} y={frame.project(centreOf(r.ring))[1]} fontSize={12} fill={p.text} textAnchor="middle">
              {r.label}
            </SvgText>
          )}
        </React.Fragment>
      ))}
    </Svg>
  );
}
