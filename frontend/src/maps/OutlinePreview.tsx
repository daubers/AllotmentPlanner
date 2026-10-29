import { useMemo } from "react";
import { frameFor, ringOf } from "../plantings/geometry";

/** A small picture of the outline a GPX trace gave, north up, so a wrong or tiny result is obvious. */
export default function OutlinePreview({ polygon, label }: { polygon: { coordinates?: unknown }; label: string }) {
  const ring = useMemo(() => ringOf(polygon), [polygon]);
  const frame = useMemo(() => (ring.length ? frameFor(ring, { width: 360, height: 180, padding: 12 }) : null), [ring]);
  if (!frame) return null;
  const d = `M${ring.map((p) => frame.project(p).map((n) => n.toFixed(1)).join(",")).join("L")}Z`;
  return (
    <svg viewBox={`0 0 ${frame.width} ${frame.height}`} role="img" aria-label={label} className="sketch outline-preview">
      <path d={d} className="bed-outline" />
    </svg>
  );
}
