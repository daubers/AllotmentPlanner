import { useState } from "react";
import { groupTasks, type Task } from "../tasks/group";
import TaskDialog from "../tasks/TaskDialog";
import { useFeatureOptions, useTaskActions, useTasks } from "../tasks/hooks";
import { useTrays } from "../trays/hooks";
import { useAllotment } from "./AllotmentLayout";

export default function TasksPage() {
  const { id, canEdit } = useAllotment();
  const tasks = useTasks(id);
  const features = useFeatureOptions(id);
  const trays = useTrays(id);
  const actions = useTaskActions(id);
  const [showDone, setShowDone] = useState(false);
  const [dialog, setDialog] = useState<Task | "new" | null>(null);

  const featureName = (fid?: number | null) => features.data?.find((f) => f.id === fid)?.name;
  const trayName = (tid?: number | null) => trays.data?.find((t) => t.id === tid)?.name;
  const groups = groupTasks(tasks.data ?? []);

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
        <button type="button" className="task-title link" onClick={() => setDialog(t)}>{t.title}</button>
        <span className="task-meta">
          {featureName(t.feature_id) && <span>📍 {featureName(t.feature_id)}</span>}
          {trayName(t.tray_id) && <span>🌱 {trayName(t.tray_id)}</span>}
          {t.planting_id && <span>🌿 planting</span>}
          {t.location && !t.feature_id && <span>📍 pinned</span>}
          {t.due_date && <span>📅 {t.due_date}</span>}
          {t.recurrence && <span>🔁 {t.recurrence}</span>}
          {t.priority === "high" && <span className="badge high">high</span>}
        </span>
      </div>
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
        <p><button type="button" onClick={() => setDialog("new")}>+ New task</button></p>
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
      {dialog && (
        <TaskDialog
          allotmentId={id}
          canEdit={canEdit}
          task={dialog === "new" ? undefined : dialog}
          onClose={() => setDialog(null)}
        />
      )}
    </main>
  );
}
