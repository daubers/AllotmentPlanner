import React from "react";
import Svg, { Circle, Line, Polygon, Polyline, Text as SvgText } from "react-native-svg";
import { layout, layoutTogether, toLocal, type Layout } from "./sketch";
import { useStyles } from "../ui/kit";

type Geometry = { type: string; coordinates: any } | undefined;

/** The corners of a drawn shape as [lon, lat] pairs, without a polygon's repeated closing point. */
export function cornersOf(geometry: Geometry): [number, number][] {
  if (!geometry) return [];
  if (geometry.type === "Polygon") return geometry.coordinates[0].slice(0, -1).map((c: number[]) => [c[0], c[1]]);
  if (geometry.type === "LineString") return geometry.coordinates.map((c: number[]) => [c[0], c[1]]);
  return [[geometry.coordinates[0], geometry.coordinates[1]]];
}

type Props = {
  geometry: Geometry;
  /** The two corners being measured (0-based), drawn bold. */
  highlight?: [number, number];
  width: number;
  height?: number;
};

/** A shape with numbered corners; the pair being measured is drawn bold. */
export function Sketch({ geometry, highlight, width, height = 220 }: Props) {
  const { palette } = useStyles();
  const corners = cornersOf(geometry);
  if (corners.length === 0) return null;
  const l = layout(toLocal(corners), width, height);
  return <Outline l={l} closed={geometry?.type === "Polygon"} highlight={highlight} stroke={palette.muted} accent={palette.accent} text={palette.text} />;
}

function Outline({
  l,
  closed,
  highlight,
  stroke,
  accent,
  text,
  dashed,
  numbers = true,
}: {
  l: Layout;
  closed: boolean;
  highlight?: [number, number];
  stroke: string;
  accent: string;
  text: string;
  dashed?: boolean;
  numbers?: boolean;
}) {
  const pts = l.points.map((p) => `${p.x},${p.y}`).join(" ");
  const single = l.points.length === 1;
  return (
    <>
      {single ? (
        <Circle cx={l.points[0].x} cy={l.points[0].y} r={5} fill={accent} />
      ) : closed ? (
        <Polygon points={pts} fill="none" stroke={stroke} strokeWidth={2} strokeDasharray={dashed ? "6 5" : undefined} />
      ) : (
        <Polyline points={pts} fill="none" stroke={stroke} strokeWidth={2} strokeDasharray={dashed ? "6 5" : undefined} />
      )}
      {highlight && !single ? (
        <Line
          x1={l.points[highlight[0]].x}
          y1={l.points[highlight[0]].y}
          x2={l.points[highlight[1]].x}
          y2={l.points[highlight[1]].y}
          stroke={accent}
          strokeWidth={6}
          strokeLinecap="round"
        />
      ) : null}
      {numbers
        ? l.points.map((p, i) => {
            const on = highlight && (highlight[0] === i || highlight[1] === i);
            return (
              <React.Fragment key={i}>
                <Circle cx={p.x} cy={p.y} r={on ? 5 : 3} fill={on ? accent : stroke} />
                <SvgText
                  x={l.labels[i].x}
                  y={l.labels[i].y + 5}
                  fontSize={on ? 17 : 14}
                  fontWeight={on ? "700" : "400"}
                  fill={on ? accent : text}
                  textAnchor="middle"
                >
                  {i + 1}
                </SvgText>
              </React.Fragment>
            );
          })
        : null}
    </>
  );
}

/** The drawn outline (dashed grey) and the corrected one (solid green) on a common scale. */
export function Compare({ drawn, corrected, width, height = 200 }: { drawn: Geometry; corrected: Geometry; width: number; height?: number }) {
  const { palette } = useStyles();
  const a = cornersOf(drawn);
  const b = cornersOf(corrected);
  if (!a.length || !b.length) return null;
  const lat0 = a.reduce((s, c) => s + c[1], 0) / a.length;
  const lng0 = a.reduce((s, c) => s + c[0], 0) / a.length;
  // Same origin for both so that a shift between them shows.
  const shift = (cs: [number, number][]) => cs.map(([x, y]) => [x - lng0 + a[0][0], y - lat0 + a[0][1]] as [number, number]);
  const [la, lb] = layoutTogether([toLocal(shift(a)), toLocal(shift(b))], width, height);
  const closed = drawn?.type === "Polygon";
  return (
    <>
      <Outline l={la} closed={closed} stroke={palette.muted} accent={palette.accent} text={palette.text} dashed numbers={false} />
      <Outline l={lb} closed={closed} stroke={palette.accent} accent={palette.accent} text={palette.text} />
    </>
  );
}
