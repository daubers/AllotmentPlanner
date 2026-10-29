import { Link } from "react-router-dom";
import { areaLabel, areaM2 } from "../plantings/geometry";
import { useBeds, usePlantings } from "../plantings/hooks";
import { useAllotment } from "./AllotmentLayout";

export default function BedsPage() {
  const { id } = useAllotment();
  const beds = useBeds(id);
  const growing = usePlantings(id, { growing: true });
  const perBed = new Map<number, number>();
  for (const p of growing.data ?? []) perBed.set(p.feature_id!, (perBed.get(p.feature_id!) ?? 0) + 1);

  return (
    <main className="page wide">
      <h1>Beds</h1>
      <p className="muted">What is growing where. Open a bed to sketch what you sowed or planted out, and to follow it through the season.</p>
      {beds.isLoading ? (
        <p className="muted">Loading…</p>
      ) : !beds.data?.length ? (
        <p className="muted">No beds yet. Draw a bed as an area on the Map (kind: bed) and it will appear here.</p>
      ) : (
        <ul className="packets">
          {beds.data.map((b) => {
            const n = perBed.get(b.id) ?? 0;
            return (
              <li key={b.id}>
                <Link to={String(b.id)} className="packet-card">
                  <span className="packet-main">
                    <strong>{b.name}</strong>
                    <span className="muted">{areaLabel(areaM2(b.ring))}</span>
                  </span>
                  <span className="badge">{n === 0 ? "Empty" : `${n} growing`}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </main>
  );
}
