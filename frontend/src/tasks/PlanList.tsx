import { useState } from "react";
import { DEFAULT_FILTERS, filterTasks } from "./filter";
import { useDayListActions, type DayList } from "./dayLists";
import { useTasks } from "./hooks";
import { longDate } from "./today";

/** Pick open jobs to put on a list: search, tick, add. Screen only. */
export default function PlanList({ allotmentId, list }: { allotmentId: number; list: DayList }) {
  const tasks = useTasks(allotmentId);
  const actions = useDayListActions(allotmentId);
  const [q, setQ] = useState("");
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const [error, setError] = useState<string | null>(null);

  const onList = new Set(list.task_ids ?? []);
  const open = filterTasks(tasks.data ?? [], { ...DEFAULT_FILTERS, q }, null).filter((t) => t.status !== "done" && !onList.has(t.id!));
  const toggle = (id: number) =>
    setPicked((s) => {
      const next = new Set(s);
      if (!next.delete(id)) next.add(id);
      return next;
    });

  async function add() {
    try {
      await actions.addTasks.mutateAsync({ id: list.id!, taskIds: [...picked] });
      setPicked(new Set());
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <details className="plan-list no-print">
      <summary>Add jobs to {list.name}</summary>
      <input type="search" aria-label="Search the jobs" placeholder="Search" value={q} onChange={(e) => setQ(e.target.value)} />
      {open.length === 0 ? (
        <p className="muted">{tasks.isLoading ? "Loading…" : "No open jobs left to add."}</p>
      ) : (
        <ul className="plan-tasks">
          {open.map((t) => (
            <li key={t.id}>
              <label className="check">
                <input type="checkbox" checked={picked.has(t.id!)} onChange={() => toggle(t.id!)} />
                {t.title}
                {t.due_date && <span className="muted"> · due {longDate(t.due_date)}</span>}
              </label>
            </li>
          ))}
        </ul>
      )}
      <button type="button" disabled={picked.size === 0 || actions.addTasks.isPending} onClick={() => void add()}>
        Add {picked.size || ""} to list
      </button>
      {error && <p role="alert" className="error">{error}</p>}
    </details>
  );
}
