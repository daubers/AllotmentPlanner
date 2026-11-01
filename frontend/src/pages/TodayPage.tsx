import { useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { buildSketch, type SketchFeature } from "../map/sketch";
import { usePlantings } from "../plantings/hooks";
import { localDate, type Task } from "../tasks/group";
import DayListsDialog from "../tasks/DayListsDialog";
import { useDayListActions, useDayListSheet, useDayLists, useSelectedList } from "../tasks/dayLists";
import { useTaskActions, useTodo } from "../tasks/hooks";
import PlanList from "../tasks/PlanList";
import { daysBetween, flatten, groupByLocation, longDate, type Places, type SheetFeature } from "../tasks/today";
import { useTrays } from "../trays/hooks";
import { useAllotment } from "./AllotmentLayout";

export default function TodayPage() {
  const { id, canEdit } = useAllotment();
  const [params, setParams] = useSearchParams();
  const date = params.get("date") || localDate();
  const includeUndated = params.get("undated") === "1";
  const lists = useDayLists(id);
  const [, selectList] = useSelectedList(id);
  const [managing, setManaging] = useState(false);
  // A list in the URL (?list=3) replaces "everything due" with that list; an unknown id falls back.
  const requested = Number(params.get("list")) || null;
  const list = lists.data?.find((l) => l.id === requested) ?? null;
  const listId = list?.id ?? null;
  const todo = useTodo(id, date, includeUndated);
  const listSheet = useDayListSheet(id, listId);
  const sheet = listId != null ? listSheet : todo;

  const set = (key: string, value: string | null) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };

  return (
    <main className="page wide today">
      <div className="no-print today-controls">
        <label>
          List
          <select
            value={listId ?? ""}
            onChange={(e) => {
              set("list", e.target.value || null);
              if (e.target.value) selectList(Number(e.target.value));
            }}
          >
            <option value="">Everything due</option>
            {(lists.data ?? []).map((l) => (
              <option key={l.id} value={l.id}>{l.name}{l.date ? ` (${l.date})` : ""}</option>
            ))}
          </select>
        </label>
        {listId == null && (
          <>
            <label>
              Date
              <input type="date" value={date} onChange={(e) => e.target.value && set("date", e.target.value)} />
            </label>
            <label className="check">
              <input type="checkbox" checked={includeUndated} onChange={(e) => set("undated", e.target.checked ? "1" : null)} />
              Include jobs with no date
            </label>
          </>
        )}
        <button type="button" className="secondary" onClick={() => setManaging(true)}>{canEdit ? "Manage lists" : "Lists"}</button>
        <button onClick={() => window.print()} disabled={!sheet.data}>🖨 Print</button>
      </div>
      {managing && (
        <DayListsDialog
          allotmentId={id}
          canEdit={canEdit}
          onClose={() => setManaging(false)}
          onCreated={(made) => {
            set("list", String(made.id));
            selectList(made.id!);
          }}
        />
      )}
      {list && canEdit && <PlanList allotmentId={id} list={list} />}

      {sheet.isLoading && <p className="muted">Loading…</p>}
      {sheet.data && (
        <Sheet key={`${listId}:${date}:${includeUndated}`} allotmentId={id} date={listId != null ? sheet.data.date ?? date : date} data={sheet.data} listId={listId} />
      )}
    </main>
  );
}

type TodoData = NonNullable<ReturnType<typeof useTodo>["data"]>;

/** The day's list. Ticking a job here completes it but keeps it on the sheet, struck through, until the date changes. */
function Sheet({ allotmentId, date, data, listId = null }: { allotmentId: number; date: string; data: TodoData; listId?: number | null }) {
  const { canEdit } = useAllotment();
  const actions = useTaskActions(allotmentId);
  const listActions = useDayListActions(allotmentId);
  const trays = useTrays(allotmentId);
  const plantings = usePlantings(allotmentId, { growing: true });
  // Jobs ticked on this sheet, and whether they are still ticked (an unticked one stays until the list refreshes).
  const [touched, setTouched] = useState<Map<number, { task: Task; done: boolean }>>(new Map());
  const order = useRef(new Map<number, number>()); // first-seen position, so a ticked job stays where it was

  const open = data.tasks ?? [];
  for (const t of open) if (!order.current.has(t.id!)) order.current.set(t.id!, order.current.size);
  const tasks = [...open, ...[...touched.values()].map((x) => x.task).filter((t) => !open.some((o) => o.id === t.id))].sort(
    (a, b) => order.current.get(a.id!)! - order.current.get(b.id!)!,
  );

  const places: Places = {
    trays: (trays.data ?? []).map((t) => ({ id: t.id!, name: t.name! })),
    plantings: (plantings.data ?? []).map((p) => ({ id: p.id!, label: `${p.packet_name || "Planting"} in ${p.bed_name}`, feature_id: p.feature_id! })),
  };
  const features = (data.features ?? []) as unknown as (SketchFeature & SheetFeature)[];
  const sections = groupByLocation(tasks, features, places);
  const ordered = flatten(sections);
  const number = new Map(ordered.map((t, i) => [t.id, i + 1]));
  const sketch = buildSketch(features, ordered);
  const who = new Map((data.members ?? []).map((m) => [m.user_id, m.display_name]));

  // A list keeps finished jobs on it, so those start out ticked.
  const isTicked = (t: Task) => touched.get(t.id!)?.done ?? t.status === "done";
  const tick = (t: Task) => {
    const done = !isTicked(t);
    (done ? actions.complete : actions.reopen).mutate(t.id!);
    setTouched((m) => new Map(m).set(t.id!, { task: { ...t, status: done ? "done" : "todo" }, done }));
  };

  return (
    <article className="sheet" aria-label="Todo list">
      <header>
        <h1>{data.title ?? data.allotment?.name}</h1>
        <p className="sheet-date">{data.title ? `${data.allotment?.name} · ` : ""}{longDate(date)}</p>
      </header>

      {sketch.shapes.length > 0 && (
        <svg className="sketch" viewBox={`0 0 ${sketch.width} ${sketch.height}`} role="img" aria-label="Sketch of the plot with numbered jobs">
          {sketch.shapes.map((s) =>
            s.type === "point" ? (
              <circle key={s.id} cx={s.x} cy={s.y} r={s.r} fill={s.colour} fillOpacity={0.35} stroke={s.colour} strokeWidth={2} />
            ) : (
              <path key={s.id} d={s.d} fill={s.type === "polygon" ? s.colour : "none"} fillOpacity={0.25} stroke={s.colour} strokeWidth={2} />
            ),
          )}
          {sketch.shapes.map(
            (s) =>
              s.label && (
                <text key={`l${s.id}`} className="sketch-label" x={s.labelAt[0]} y={s.labelAt[1]} textAnchor="middle">
                  {s.label}
                </text>
              ),
          )}
          {sketch.pins.map((p) => (
            <g key={p.taskId} transform={`translate(${p.x} ${p.y})`}>
              <circle r={12} className="pin-bg" />
              <text className="pin-n" textAnchor="middle" dy="0.35em">{p.n}</text>
            </g>
          ))}
        </svg>
      )}

      {ordered.length === 0 ? (
        <p className="all-clear">{listId != null ? "Nothing on this list yet. Add jobs above, or from the Tasks page." : "Nothing due. Enjoy the plot! 🌱"}</p>
      ) : (
        sections.map((section) => (
          <section key={section.title} className="sheet-section">
            <h2>{section.to ? <Link to={`../${section.to}`}>{section.title}</Link> : section.title}</h2>
            <ol className="sheet-tasks">
              {section.tasks.map((t) => {
                const late = t.due_date ? daysBetween(t.due_date, date) : 0;
                const isDone = isTicked(t);
                return (
                  <li key={t.id} className={isDone ? "ticked" : undefined}>
                    <span className="box" aria-hidden="true" />
                    {canEdit && (
                      <input
                        type="checkbox"
                        className="tick no-print"
                        aria-label={`${isDone ? "Reopen" : "Complete"} ${t.title}`}
                        checked={isDone}
                        onChange={() => tick(t)}
                      />
                    )}
                    <span className="num">{number.get(t.id)}</span>
                    <span className="what">
                      <strong>{t.title}</strong>
                      {t.priority === "high" && <em className="flag"> high priority</em>}
                      {late > 0 && !isDone && <em className="flag"> overdue by {late} day{late > 1 ? "s" : ""}</em>}
                      {t.recurrence && <em> · repeats {t.recurrence}</em>}
                      {t.assignee_id != null && who.get(t.assignee_id) && <em> · {who.get(t.assignee_id)}</em>}
                      {t.description && <span className="notes">{t.description}</span>}
                    </span>
                    {canEdit && listId != null && (
                      <button type="button" className="link no-print remove-from-list" aria-label={`Take ${t.title} off the list`} onClick={() => listActions.removeTask.mutate({ id: listId, taskId: t.id! })}>✕</button>
                    )}
                  </li>
                );
              })}
            </ol>
          </section>
        ))
      )}
      <footer className="sheet-foot">{ordered.length} job{ordered.length === 1 ? "" : "s"} · printed {new Date().toLocaleString("en-GB")}</footer>
    </article>
  );
}
