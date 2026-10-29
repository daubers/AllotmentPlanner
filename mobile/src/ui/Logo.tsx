import React from "react";
import Svg, { Circle, Ellipse, Path } from "react-native-svg";
import { usePalette } from "./theme";

/** The Allotment mark: a map pin with a seedling in it (docs/brand/logo.svg). */
export function Logo({ size = 72 }: { size?: number }) {
  const p = usePalette();
  return (
    <Svg width={size} height={size} viewBox="0 0 512 512" accessibilityLabel="Allotment" accessibilityRole="image">
      <Ellipse cx={256} cy={450} rx={92} ry={20} fill={p.accent} opacity={0.18} />
      <Path d="M256 448 C256 448 120 328 120 226 A136 136 0 0 1 392 226 C392 328 256 448 256 448 Z" fill={p.accent} />
      <Circle cx={256} cy={226} r={86} fill={p.surface} />
      <Path d="M256 276 L256 196" stroke={p.accent} strokeWidth={16} strokeLinecap="round" fill="none" />
      <Path d="M256 236 C220 238 192 214 190 176 C230 174 258 198 256 236 Z" fill={p.accent} />
      <Path d="M256 204 C256 176 272 160 300 158 C302 186 284 204 256 204 Z" fill="#2f8a52" />
    </Svg>
  );
}
