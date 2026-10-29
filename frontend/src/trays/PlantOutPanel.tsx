import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { colourOf, polygonOf, ringOf, type LonLat } from "../plantings/geometry";
import { useBeds, usePlantings, usePlantOut } from "../plantings/hooks";
import RegionEditor from "../plantings/RegionEditor";
import { posOf } from "./grid";

const today = () => new Date().toISOString().slice(0, 10);

/** Plant the selected tray cells out into a drawn area of a bed. One planting is made per kind of seed. */
export default function PlantOutPanel({ allotmentId, trayId, selected, onDone }: { allotmentId: number; trayId: number; selected: ReadonlySet<string>; onDone(): void }) {
  const navigate = useNavigate();
  const beds = useBeds(allotmentId);
  const [bedId, setBedId] = useState<number | "">("");
  const [points, setPoints] = useState<LonLat[]>([]);
  const [error, setError] = useState<string | null>(null);
  const plantOut = usePlantOut(allotmentId);
  const bed = beds.data?.find((b) => b.id === bedId);
  const there = usePlantings(allotmentId, { featureId: bed?.id, growing: true });
  const n = selected.size;

  async function go(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!bed) return;
    const f = new FormData(e.currentTarget);
    try {
      await plantOut.mutateAsync({
        trayId,
        cells: [...selected].map(posOf),
        feature_id: bed.id,
        region: polygonOf(points),
        planted_on: String(f.get("planted_on") || today()),
        notes: String(f.get("notes") ?? "").trim(),
      });
      onDone();
      navigate(`../../beds/${bed.id}`, { relative: "path" });
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <section className="tray-actions" aria-label="Plant out the selected cells">
      <h2>Plant out {n} cell{n === 1 ? "" : "s"}</h2>
      <form onSubmit={(e) => void go(e)} className="planting-form">
        <label>
          Into which bed
          <select value={bedId} onChange={(e) => { setBedId(e.target.value ? Number(e.target.value) : ""); setPoints([]); setError(null); }}>
            <option value="">Choose a bed…</option>
            {(beds.data ?? []).map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
        </label>
        <label>Planted on<input name="planted_on" type="date" defaultValue={today()} /></label>
        <label className="wide">Notes<input name="notes" maxLength={5000} placeholder="optional" /></label>
        {bed && (
          <div className="wide">
            <p className="muted">Click the corners of the area they go in.</p>
            <RegionEditor
              bed={bed.ring}
              others={(there.data ?? []).map((p) => ({ id: p.id!, label: p.packet_name ?? "Unknown seed", ring: ringOf(p.region), colour: colourOf(p.packet_id), muted: true }))}
              points={points}
              onChange={setPoints}
              title={`Sketch of ${bed.name}`}
            />
          </div>
        )}
        {error && <p role="alert" className="error wide">{error}</p>}
        <button type="submit" disabled={!bed || points.length < 3 || plantOut.isPending}>Plant out</button>
      </form>
    </section>
  );
}
