import { useState } from "react";
import { groupTasks, type Task } from "../tasks/group";
import { useFeatureOptions, useTaskActions, useTasks } from "../tasks/hooks";
import { useAllotment } from "./AllotmentLayout";

const PRIORITIES = ["low", "normal", "high"] as const;
const RECURRENCES = ["daily", "weekly", "monthly"] as const;

export default function TasksPage() {
  const { id, canEdit } = useAllotment();
  const tasks = useTasks(id);
  const features = useFeatureOptions(id);
  const actions = useTaskActions(id);
  const [showDone, setShowDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const featureName = (fid?: number | null) => features.data?.find((f) => f.id === fid)?.name;
  const groups = groupTasks(tasks.data ?? []);

  async function add(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    const text = (k: string) => String(f.get(k) ?? "");
    try {
      await actions.create.mutateAsync({
        title: text("title").trim(),
        due_date: text("due_date") || null,
        priority: text("priority") as (typeof PRIORITIES)[number],
        feature_id: text("feature_id") ? Number(text("feature_id")) : null,
        recurrence: (text("recurrence") || null) as (typeof RECURRENCES)[number] | null,
      });
      form.reset();
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  const row = (t: Task) => (
    <li key={t.id} className={`task ${t.status === "done" ? "done" : ""}`}>
      <input
        type="checkbox"
        aria-label={`${t.status === "done" ? "Reopen" : "Complete"} ${t.title}`}
        checked={t.status === "done"}
        disabled={!canEdit}
        onChange={() => (t.status === "done" ? actions.reopen : actions.complete).mutate(t.id!)}
      />
      <div className="task-main">
        <span className="task-title">{t.title}</span>
        <span className="task-meta">
          {featureName(t.feature_id) && <span>📍 {featureName(t.feature_id)}</span>}
          {t.location && !t.feature_id && <span>📍 pinned</span>}
          {t.due_date && <span>📅 {t.due_date}</span>}
          {t.recurrence && <span>🔁 {t.recurrence}</span>}
          {t.priority === "high" && <span className="badge high">high</span>}
        </span>
      </div>
      {canEdit && (
        <button className="link" aria-label={`Delete ${t.title}`} onClick={() => actions.remove.mutate(t.id!)}>
          ✕
        </button>
      )}
    </li>
  );

  const section = (title: string, list: Task[], cls = "") =>
    list.length > 0 && (
      <section className={cls}>
        <h2>{title} <span className="muted">({list.length})</span></h2>
        <ul className="tasks">{list.map(row)}</ul>
      </section>
    );

  const empty = tasks.data && groups.overdue.length + groups.today.length + groups.upcoming.length + groups.undated.length === 0;

  return (
    <main className="page wide">
      <h1>Tasks</h1>
      {canEdit ? (
        <form className="task-form" onSubmit={add}>
          <input name="title" placeholder="What needs doing?" aria-label="Task title" required maxLength={200} />
          <input name="due_date" type="date" aria-label="Due date" />
          <select name="priority" defaultValue="normal" aria-label="Priority">
            {PRIORITIES.map((p) => <option key={p}>{p}</option>)}
          </select>
          <select name="feature_id" aria-label="Location" defaultValue="">
            <option value="">No location</option>
            {features.data?.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
          </select>
          <select name="recurrence" aria-label="Repeats" defaultValue="">
            <option value="">Doesn't repeat</option>
            {RECURRENCES.map((r) => <option key={r}>{r}</option>)}
          </select>
          <button type="submit" disabled={actions.create.isPending}>Add task</button>
          {error && <p role="alert" className="error">{error}</p>}
        </form>
      ) : (
        <p className="muted">View only: ask an owner for editor access to add or complete tasks.</p>
      )}
      {tasks.isLoading && <p className="muted">Loading…</p>}
      {empty && <p className="muted">Nothing to do. Enjoy the sunshine ☀️</p>}
      {section("Overdue", groups.overdue, "overdue")}
      {section("Today", groups.today)}
      {section("Upcoming", groups.upcoming)}
      {section("No date", groups.undated)}
      {groups.done.length > 0 && (
        <p><button className="link" onClick={() => setShowDone(!showDone)}>{showDone ? "Hide" : "Show"} completed ({groups.done.length})</button></p>
      )}
      {showDone && section("Completed", groups.done)}
    </main>
  );
}
