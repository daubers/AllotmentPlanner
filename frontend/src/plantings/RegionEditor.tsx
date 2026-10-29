import { useMemo, useRef, useState } from "react";
import { areaLabel, areaM2, colourOf, frameFor, polygonOf, ringOf, withinBed, type LonLat } from "./geometry";

export type Shown = { id: number; label: string; ring: LonLat[]; colour: string; muted?: boolean };

type Props = {
  bed: LonLat[];
  /** Plantings already in the bed, drawn behind the one being made. */
  others?: Shown[];
  /** The corners clicked so far (an open ring). */
  points: LonLat[];
  onChange?(points: LonLat[]): void;
  /** Without ``onChange`` the sketch is just a picture; ``onPick`` makes the shapes clickable. */
  onPick?(id: number): void;
  selectedId?: number | null;
  title?: string;
};

/** A sketch of one bed. To plant, click the corners of the area; it closes itself. */
export default function RegionEditor({ bed, others = [], points, onChange, onPick, selectedId, title = "Sketch of the bed" }: Props) {
  const frame = useMemo(() => frameFor(bed), [bed]);
  const svg = useRef<SVGSVGElement>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const toPath = (ring: LonLat[]) => (ring.length ? `M${ring.map((p) => frame.project(p).map((n) => n.toFixed(1)).join(",")).join("L")}Z` : "");
  const editable = !!onChange;

  function click(e: React.MouseEvent<SVGSVGElement>) {
    if (!onChange || !svg.current) return;
    const box = svg.current.getBoundingClientRect();
    const at = frame.unproject([((e.clientX - box.left) / box.width) * frame.width, ((e.clientY - box.top) / box.height) * frame.height]);
    if (!withinBed(at, bed)) {
      setProblem("That corner is outside the bed.");
      return;
    }
    setProblem(null);
    onChange([...points, at]);
  }

  return (
    <div className="region-editor">
      <svg
        ref={svg}
        viewBox={`0 0 ${frame.width} ${frame.height}`}
        role="img"
        aria-label={`${title}${editable ? ". Click the corners of the area you are planting." : ""}`}
        className={editable ? "sketch drawing" : "sketch"}
        onClick={click}
      >
        <path d={toPath(bed)} className="bed-outline" />
        {others.map((o) => (
          <g key={o.id} className={o.id === selectedId ? "region selected" : "region"} opacity={o.muted ? 0.35 : 1}>
            <path
              d={toPath(o.ring)}
              fill={o.colour}
              fillOpacity={0.55}
              stroke={o.colour}
              strokeWidth={o.id === selectedId ? 3 : 1.5}
              onClick={onPick ? (ev) => { ev.stopPropagation(); onPick(o.id); } : undefined}
              style={onPick ? { cursor: "pointer" } : undefined}
            >
              <title>{o.label}</title>
            </path>
            {o.ring.length > 0 && (
              <text x={frame.project(centreOf(o.ring))[0]} y={frame.project(centreOf(o.ring))[1]} className="region-label" textAnchor="middle">
                {o.label}
              </text>
            )}
          </g>
        ))}
        {points.length > 0 && (
          <g className="drawing-shape">
            <path d={toPath(points)} fill="#2f7d3b" fillOpacity={0.35} stroke="#2f7d3b" strokeWidth={2} strokeDasharray={points.length < 3 ? "4 3" : undefined} />
            {points.map((p, i) => (
              <circle key={i} cx={frame.project(p)[0]} cy={frame.project(p)[1]} r={4} fill="#fff" stroke="#2f7d3b" strokeWidth={2} />
            ))}
          </g>
        )}
      </svg>
      {editable && (
        <div className="inline region-tools">
          <button type="button" className="secondary" disabled={points.length === 0} onClick={() => onChange([...points.slice(0, -1)])}>Undo last corner</button>
          <button type="button" className="secondary" disabled={points.length === 0} onClick={() => { setProblem(null); onChange([]); }}>Clear</button>
          <button type="button" className="secondary" onClick={() => { setProblem(null); onChange(bed); }}>Whole bed</button>
          <span className="muted" role="status">
            {points.length === 0 ? "Click the corners of the area." : points.length < 3 ? `${points.length} corner${points.length === 1 ? "" : "s"}: add at least 3.` : areaLabel(areaM2(points))}
          </span>
        </div>
      )}
      {problem && <p role="alert" className="error">{problem}</p>}
    </div>
  );
}

function centreOf(ring: LonLat[]): LonLat {
  const lons = ring.map((p) => p[0]);
  const lats = ring.map((p) => p[1]);
  return [(Math.min(...lons) + Math.max(...lons)) / 2, (Math.min(...lats) + Math.max(...lats)) / 2];
}

export { colourOf, polygonOf, ringOf };
