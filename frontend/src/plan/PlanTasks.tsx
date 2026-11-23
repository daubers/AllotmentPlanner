import { useState } from "react";
import { dayLabel } from "./window";
import { usePlanTaskActions, usePlanTasks, type PlanBed } from "./hooks";

/** The jobs the plan implies, to add as tasks, and a prompt when tasks made earlier no longer match the plan. */
export default function PlanTasks({
  allotmentId,
  beds,
  featureId,
  canEdit,
  onMaintenance,
}: {
  allotmentId: number;
  beds: PlanBed[];
  featureId: number | null;
  canEdit: boolean;
  onMaintenance(): void;
}) {
  const tasks = usePlanTasks(allotmentId, featureId);
  const actions = usePlanTaskActions(allotmentId);
  const [skip, setSkip] = useState<Set<string>>(new Set()); // unticked
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const suggestions = tasks.data?.suggestions ?? [];
  const fresh = suggestions.filter((s) => !s.added);
  const chosen = fresh.filter((s) => !skip.has(s.key!));
  const stale = tasks.data?.stale ?? 0;
  const bedName = (id?: number) => beds.find((b) => b.feature_id === id)?.name ?? "A bed";
  const byBed = [...new Set(fresh.map((s) => s.feature_id!))];

  const toggle = (key: string) =>
    setSkip((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  async function add() {
    setError(null);
    try {
      const made = await actions.add.mutateAsync({ keys: chosen.map((s) => s.key!), featureId });
      setMessage(`Added ${made.length} task${made.length === 1 ? "" : "s"}. You will find them on the Tasks and Today pages.`);
      setSkip(new Set());
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function update() {
    setError(null);
    try {
      const r = await actions.sync.mutateAsync(featureId);
      const [updated, removed] = [r.updated ?? 0, r.removed ?? 0];
      setMessage(`Updated ${updated} and removed ${removed} task${updated + removed === 1 ? "" : "s"} to match the plan.`);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <section className="plan-tasks" aria-label="Tasks from the plan">
      <header>
        <h2>Tasks from the plan</h2>
        {canEdit && (
          <button type="button" className="secondary" onClick={onMaintenance}>
            Add a repeating job
          </button>
        )}
      </header>
      {stale > 0 && (
        <p role="status" className="plan-stale">
          {stale} task{stale === 1 ? "" : "s"} made from the plan {stale === 1 ? "is" : "are"} out of date.{" "}
          {canEdit && (
            <button type="button" onClick={() => void update()} disabled={actions.sync.isPending}>
              Update {stale === 1 ? "it" : "them"}
            </button>
          )}
        </p>
      )}
      {tasks.isLoading ? (
        <p className="muted">Working it out…</p>
      ) : fresh.length === 0 ? (
        <p className="muted">
          {suggestions.length > 0 ? "Every job from the plan is already a task." : "Nothing to add yet. Plan a crop above and its sowing, planting out and clearing jobs appear here."}
        </p>
      ) : (
        byBed.map((id) => (
          <div key={id} className="plan-task-group">
            {byBed.length > 1 || featureId === null ? <h3>{bedName(id)}</h3> : null}
            <ul className="suggested-tasks">
              {fresh
                .filter((s) => s.feature_id === id)
                .map((s) => (
                  <li key={s.key}>
                    <label className="check">
                      <input type="checkbox" checked={!skip.has(s.key!)} onChange={() => toggle(s.key!)} disabled={!canEdit} />
                      <span>
                        <strong>{s.title}</strong>
                        <span className="muted"> · {dayLabel(s.due_date!)}</span>
                      </span>
                    </label>
                  </li>
                ))}
            </ul>
          </div>
        ))
      )}
      {message && <p role="status">{message}</p>}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {canEdit && fresh.length > 0 && (
        <button type="button" disabled={chosen.length === 0 || actions.add.isPending} onClick={() => void add()}>
          Add {chosen.length} task{chosen.length === 1 ? "" : "s"}
        </button>
      )}
    </section>
  );
}
