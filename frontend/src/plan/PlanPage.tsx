import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useAllotment } from "../pages/AllotmentLayout";
import MaintenanceDialog from "./MaintenanceDialog";
import PlanItemDialog from "./PlanItemDialog";
import PlanTasks from "./PlanTasks";
import PlanTimeline from "./PlanTimeline";
import { mergeConflicts } from "./conflicts";
import { usePlan, type PlanBed, type PlanItem } from "./hooks";
import { currentKey, makeWindow, parseKey, shiftMonth } from "./window";

type Editing = { bed: PlanBed; item?: PlanItem };

/** What to grow in each bed over twelve months, as bars on a timeline. The window moves a month at a time. */
export default function PlanPage() {
  const { id, canEdit } = useAllotment();
  const [params, setParams] = useSearchParams();
  const key = parseKey(params.get("from"), currentKey());
  const win = makeWindow(key);
  const bedFilter = Number(params.get("bed")) || null;
  const plan = usePlan(id, win.from, win.to);
  const [editing, setEditing] = useState<Editing | null>(null);
  const [maintenance, setMaintenance] = useState(false);

  const go = (next: string) => {
    const p = new URLSearchParams(params);
    p.set("from", next);
    setParams(p, { replace: true });
  };
  const pickBed = (value: string) => {
    const p = new URLSearchParams(params);
    if (value) p.set("bed", value);
    else p.delete("bed");
    setParams(p, { replace: true });
  };

  const allBeds = plan.data?.beds ?? [];
  const beds = bedFilter ? allBeds.filter((b) => b.feature_id === bedFilter) : allBeds;
  const first = win.months[0];
  const last = win.months[11];

  return (
    <main className="page wide plan-page">
      <h1>Plan</h1>
      <p className="muted">
        Decide what to grow in each bed and when. Give each crop an amount of space, repeat it as a succession, and watch for months when a bed is
        overbooked.
      </p>
      <div className="toolbar plan-toolbar">
        <button type="button" className="secondary" onClick={() => go(shiftMonth(key, -1))} aria-label="Earlier">
          ◀
        </button>
        <strong aria-live="polite">
          {first.label} {first.year} – {last.label} {last.year}
        </strong>
        <button type="button" className="secondary" onClick={() => go(shiftMonth(key, 1))} aria-label="Later">
          ▶
        </button>
        <button type="button" className="secondary" onClick={() => go(currentKey())} disabled={key === currentKey()}>
          This month
        </button>
        <label className="plan-bed-pick">
          Bed
          <select value={bedFilter ?? ""} onChange={(e) => pickBed(e.target.value)}>
            <option value="">All beds</option>
            {allBeds.map((b) => (
              <option key={b.feature_id} value={b.feature_id}>
                {b.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      {plan.isLoading ? (
        <p className="muted">Loading…</p>
      ) : allBeds.length === 0 ? (
        <p className="muted">
          No beds yet. Draw a bed on the <Link to="..">Map</Link> (kind: bed) and it will appear here.
        </p>
      ) : (
        beds.map((bed) => {
          const runs = mergeConflicts(bed.conflicts);
          const clashes = runs.length;
          return (
            <section key={bed.feature_id} className="plan-bed" aria-label={bed.name}>
              <header>
                <h2>{bed.name}</h2>
                <span className="muted">{bed.area_m2 ? `about ${Math.round(bed.area_m2 * 10) / 10} m²` : "size unknown"}</span>
                {clashes > 0 && (
                  <span className="badge plan-warn" role="status">
                    Overbooked {clashes === 1 ? "once" : `${clashes} times`}
                  </span>
                )}
                {canEdit && (
                  <button type="button" onClick={() => setEditing({ bed })}>
                    Add crop
                  </button>
                )}
              </header>
              {clashes > 0 && (
                <ul className="plan-clashes">
                  {runs.map((c) => (
                    <li key={`${c.from}-${c.to}`}>
                      {c.from} to {c.to}: up to {c.peak_m2} m² planned in {Math.round((bed.area_m2 ?? 0) * 10) / 10} m² (over by {c.over_m2} m² at worst)
                    </li>
                  ))}
                </ul>
              )}
              <PlanTimeline win={win} bed={bed} onEdit={(item) => canEdit && setEditing({ bed, item })} />
            </section>
          );
        })
      )}

      {allBeds.length > 0 && (
        <PlanTasks allotmentId={id} beds={allBeds} featureId={bedFilter} canEdit={canEdit} onMaintenance={() => setMaintenance(true)} />
      )}

      {maintenance && (
        <MaintenanceDialog allotmentId={id} beds={allBeds} bedId={bedFilter} until={win.to} onClose={() => setMaintenance(false)} />
      )}

      {editing && (
        <PlanItemDialog
          allotmentId={id}
          bed={{ id: editing.bed.feature_id!, name: editing.bed.name!, area: editing.bed.area_m2 ?? null }}
          item={editing.item}
          onClose={() => setEditing(null)}
        />
      )}
    </main>
  );
}
