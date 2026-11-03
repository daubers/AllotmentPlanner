import React from "react";
import { View } from "react-native";
import Svg, { Circle, G, Polygon, Polyline, Rect, Text as SvgText } from "react-native-svg";
import { frameFor } from "../beds/geometry";
import { radius, usePalette } from "../ui/theme";
import type { Pin, Selection } from "./pins";
import { colourForKind, extentPoints, type PlotShape } from "./shapes";

const M_PER_DEG = 111_320;
// Larger things underneath: the boundary and paths first, then beds, then small things on top.
const ORDER = ["boundary", "path", "bed", "water", "compost", "shed", "tree", "other"];
const rank = (k: string) => (ORDER.indexOf(k) === -1 ? ORDER.length : ORDER.indexOf(k));

const isSelected = (sel: Selection | null | undefined, s: PlotShape) => sel?.kind === "shape" && sel.id === s.id;

/** The drawn map of the plot, north up. Tap a shape or a pin to select it; tap the ground to clear. */
export default function PlotMap({
  shapes,
  pins = [],
  selected,
  onSelect,
  height = 340,
}: {
  shapes: PlotShape[];
  pins?: Pin[];
  selected?: Selection | null;
  onSelect?: (s: Selection | null) => void;
  height?: number;
}) {
  const p = usePalette();
  const width = 340;
  // Fit to the shapes and to any pin that sits away from them, so nothing is drawn off the edge.
  const frame = frameFor([...extentPoints(shapes), ...pins.map((x) => x.point)], width, height, 22);
  const line = (points: [number, number][]) => points.map((c) => frame.project(c).map((n) => n.toFixed(1)).join(",")).join(" ");
  // Pixels per metre, from one degree of latitude, to size circles.
  const pxPerM = Math.abs(frame.project([0, 1 / M_PER_DEG])[1] - frame.project([0, 0])[1]) || 1;
  const sorted = [...shapes].sort((a, b) => rank(a.kind) - rank(b.kind));
  const pick = (s: Selection) => () => onSelect?.(s);
  const selectedKey = selected?.kind === "spot" ? selected.key : null;

  return (
    <View style={{ borderRadius: radius.lg, overflow: "hidden", backgroundColor: p.surfaceAlt, borderWidth: 1, borderColor: p.border }}>
      <Svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} accessibilityLabel="Map of your plot. Tap a bed or a pin to see its jobs.">
        <Rect x={0} y={0} width={width} height={height} fill="transparent" onPress={() => onSelect?.(null)} />
        {sorted.map((s) => {
          const colour = colourForKind(s.kind);
          const on = isSelected(selected, s);
          const sel = pick({ kind: "shape", id: s.id });
          if (s.type === "area") {
            return (
              <Polygon
                key={s.id}
                points={line(s.points)}
                fill={colour}
                fillOpacity={s.kind === "boundary" ? 0.01 : on ? 0.6 : 0.35}
                stroke={on ? p.text : colour}
                strokeWidth={on ? 3.5 : s.kind === "boundary" ? 2.5 : 2}
                onPress={sel}
              />
            );
          }
          if (s.type === "line") {
            return (
              <G key={s.id} onPress={sel}>
                <Polyline points={line(s.points)} fill="none" stroke="transparent" strokeWidth={22} strokeLinecap="round" />
                <Polyline points={line(s.points)} fill="none" stroke={on ? p.text : colour} strokeWidth={on ? 5 : 3} strokeLinecap="round" strokeLinejoin="round" />
              </G>
            );
          }
          const [cx, cy] = frame.project(s.points[0]);
          return s.radiusM ? (
            <Circle key={s.id} cx={cx} cy={cy} r={Math.max(s.radiusM * pxPerM, 12)} fill={colour} fillOpacity={on ? 0.6 : 0.35} stroke={on ? p.text : colour} strokeWidth={on ? 3.5 : 2} onPress={sel} />
          ) : (
            <G key={s.id} onPress={sel}>
              <Circle cx={cx} cy={cy} r={16} fill="transparent" />
              <Circle cx={cx} cy={cy} r={on ? 8 : 6} fill={colour} stroke={on ? p.text : p.surface} strokeWidth={on ? 3 : 1.5} />
            </G>
          );
        })}
        {pins.map((pin) => {
          const [x, y] = frame.project(pin.point);
          const fill = pin.late ? p.danger : p.accent;
          const on = pin.selection.kind === "spot" ? pin.selection.key === selectedKey : isSelected(selected, shapes.find((s) => s.id === (pin.selection as { id: number }).id) ?? ({ id: -1 } as PlotShape));
          return (
            <G key={pin.key} onPress={pick(pin.selection)} accessibilityLabel={`${pin.count} ${pin.count === 1 ? "job" : "jobs"}${pin.late ? ", some late" : ""}`}>
              <Circle cx={x} cy={y} r={20} fill="transparent" />
              <Circle cx={x} cy={y} r={on ? 14 : 12} fill={fill} stroke={p.surface} strokeWidth={2.5} />
              <SvgText x={x} y={y + 4.5} fontSize={13} fontWeight="700" fill={p.onAccent} textAnchor="middle">
                {pin.count}
              </SvgText>
            </G>
          );
        })}
      </Svg>
    </View>
  );
}
