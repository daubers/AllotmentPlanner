import { useSearchParams } from "react-router-dom";
import { buildSketch, type SketchFeature } from "../map/sketch";
import { localDate } from "../tasks/group";
import { useTodo } from "../tasks/hooks";
import { daysBetween, flatten, groupByLocation, longDate, type SheetFeature } from "../tasks/today";
import { useAllotment } from "./AllotmentLayout";

export default function TodayPage() {
  const { id } = useAllotment();
  const [params, setParams] = useSearchParams();
  const date = params.get("date") || localDate();
  const includeUndated = params.get("undated") === "1";
  const todo = useTodo(id, date, includeUndated);

  const set = (key: string, value: string | null) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };

  const features = (todo.data?.features ?? []) as unknown as (SketchFeature & SheetFeature)[];
  const sections = groupByLocation(todo.data?.tasks ?? [], features);
  const ordered = flatten(sections);
  const number = new Map(ordered.map((t, i) => [t.id, i + 1]));
  const sketch = buildSketch(features, ordered);
  const who = new Map((todo.data?.members ?? []).map((m) => [m.user_id, m.display_name]));

  return (
    <main className="page wide today">
      <div className="no-print today-controls">
        <label>
          Date
          <input type="date" value={date} onChange={(e) => e.target.value && set("date", e.target.value)} />
        </label>
        <label className="check">
          <input type="checkbox" checked={includeUndated} onChange={(e) => set("undated", e.target.checked ? "1" : null)} />
          Include jobs with no date
        </label>
        <button onClick={() => window.print()} disabled={!todo.data}>🖨 Print</button>
      </div>

      {todo.isLoading && <p className="muted">Loading…</p>}
      {todo.data && (
        <article className="sheet" aria-label="Todo list">
          <header>
            <h1>{todo.data.allotment?.name}</h1>
            <p className="sheet-date">{longDate(date)}</p>
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
            <p className="all-clear">Nothing due. Enjoy the plot! 🌱</p>
          ) : (
            sections.map((section) => (
              <section key={section.title} className="sheet-section">
                <h2>{section.title}</h2>
                <ol className="sheet-tasks">
                  {section.tasks.map((t) => {
                    const late = t.due_date ? daysBetween(t.due_date, date) : 0;
                    return (
                      <li key={t.id}>
                        <span className="box" aria-hidden="true" />
                        <span className="num">{number.get(t.id)}</span>
                        <span className="what">
                          <strong>{t.title}</strong>
                          {t.priority === "high" && <em className="flag"> high priority</em>}
                          {late > 0 && <em className="flag"> overdue by {late} day{late > 1 ? "s" : ""}</em>}
                          {t.recurrence && <em> · repeats {t.recurrence}</em>}
                          {t.assignee_id != null && who.get(t.assignee_id) && <em> · {who.get(t.assignee_id)}</em>}
                          {t.description && <span className="notes">{t.description}</span>}
                        </span>
                      </li>
                    );
                  })}
                </ol>
              </section>
            ))
          )}
          <footer className="sheet-foot">{ordered.length} job{ordered.length === 1 ? "" : "s"} · printed {new Date().toLocaleString("en-GB")}</footer>
        </article>
      )}
    </main>
  );
}
