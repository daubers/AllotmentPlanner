import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth";
import { usePlantings } from "../plantings/hooks";
import { DEFAULT_FILTERS, filterTasks, isFiltered, readFilters, rescheduleDates, writeFilters, type Filters } from "../tasks/filter";
import { groupTasks, type Task } from "../tasks/group";
import { useDayLists, useDayListActions, useSelectedList } from "../tasks/dayLists";
import ListAdd from "../tasks/ListAdd";
import PlaceOptions from "../tasks/PlaceOptions";
import TaskDialog from "../tasks/TaskDialog";
import { useFeatureOptions, useMembers, useTaskActions, useTasks } from "../tasks/hooks";
import { useTrays } from "../trays/hooks";
import { useAllotment } from "./AllotmentLayout";

export default function TasksPage() {
  const { id, canEdit, allotment } = useAllotment();
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const filters = readFilters(params);
  const tasks = useTasks(id);
  const features = useFeatureOptions(id);
  const trays = useTrays(id);
  const plantings = usePlantings(id, { growing: true });
  const members = useMembers(id);
  const actions = useTaskActions(id);
  const [showDone, setShowDone] = useState(false);
  const [dialog, setDialog] = useState<Task | "new" | null>(null);
  const [selecting, setSelecting] = useState(false);
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [added, setAdded] = useState<{ listId: number; name: string; count: number } | null>(null);
  const dayLists = useDayLists(id);
  const listActions = useDayListActions(id);
  const [selectedList] = useSelectedList(id);
  const quickList = dayLists.data?.find((l) => l.id === selectedList) ?? null;
  const listsOf = (taskId: number) => (dayLists.data ?? []).filter((l) => l.task_ids?.includes(taskId));
  const listAdded = (listId: number, name: string, count: number) => {
    setError(null);
    setAdded({ listId, name, count });
  };

  const change = (patch: Partial<Filters>) => setParams(writeFilters({ ...filters, ...patch }, params), { replace: true });
  const featureName = (fid?: number | null) => features.data?.find((f) => f.id === fid)?.name;
  const trayName = (tid?: number | null) => trays.data?.find((t) => t.id === tid)?.name;
  const who = (uid?: number | null) => members.data?.find((m) => m.user_id === uid)?.display_name;
  const shown = filterTasks(tasks.data ?? [], filters, user?.id);
  const groups = groupTasks(shown);
  const dates = rescheduleDates();

  async function run(work: () => Promise<unknown>) {
    try {
      await work();
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    }
  }
  const reschedule = (t: Task, value: string) => {
    if (!value) return;
    const due_date = value === "none" ? null : value === "tomorrow" ? dates.tomorrow : dates.nextWeek;
    void run(() => actions.update.mutateAsync({ id: t.id!, body: { due_date } }));
  };
  const leaveSelecting = () => {
    setSelecting(false);
    setPicked(new Set());
    setConfirmDelete(false);
  };
  const bulk = (action: "complete" | "reopen" | "delete" | "reschedule", due_date?: string | null) =>
    run(async () => {
      await actions.bulk.mutateAsync({ ids: [...picked], action, ...(action === "reschedule" ? { due_date } : {}) });
      leaveSelecting();
    });
  const toggle = (taskId: number) =>
    setPicked((prev) => {
      const next = new Set(prev);
      if (!next.delete(taskId)) next.add(taskId);
      return next;
    });

  const row = (t: Task) => (
    <li key={t.id} className={`task ${t.status === "done" ? "done" : ""}`}>
      {selecting && (
        <input type="checkbox" aria-label={`Select ${t.title}`} checked={picked.has(t.id!)} onChange={() => toggle(t.id!)} />
      )}
      {!selecting && (
        <input
          type="checkbox"
          aria-label={`${t.status === "done" ? "Reopen" : "Complete"} ${t.title}`}
          checked={t.status === "done"}
          disabled={!canEdit}
          onChange={() => (t.status === "done" ? actions.reopen : actions.complete).mutate(t.id!)}
        />
      )}
      <div className="task-main">
        <button type="button" className="task-title link" onClick={() => setDialog(t)}>{t.title}</button>
        <span className="task-meta">
          {featureName(t.feature_id) && <span>📍 {featureName(t.feature_id)}</span>}
          {trayName(t.tray_id) && <span>🌱 {trayName(t.tray_id)}</span>}
          {t.planting_id && <span>🌿 planting</span>}
          {t.location && !t.feature_id && <span>📍 pinned</span>}
          {t.due_date && <span>📅 {t.due_date}</span>}
          {t.recurrence && <span>🔁 {t.recurrence}</span>}
          {who(t.assignee_id) && <span>👤 {who(t.assignee_id)}</span>}
          {t.status === "doing" && <span className="badge">doing</span>}
          {t.priority === "high" && <span className="badge high">high</span>}
          {listsOf(t.id!).map((l) => (
            <span key={l.id} className="badge on-list" title={`On the list ${l.name}`}>📋 {l.name}</span>
          ))}
        </span>
      </div>
      {canEdit && !selecting && t.status !== "done" && quickList && !quickList.task_ids?.includes(t.id!) && (
        <button
          type="button"
          className="secondary quick-add"
          aria-label={`Add ${t.title} to ${quickList.name}`}
          disabled={listActions.addTasks.isPending}
          onClick={() => void run(async () => {
            await listActions.addTasks.mutateAsync({ id: quickList.id!, taskIds: [t.id!] });
            listAdded(quickList.id!, quickList.name!, 1);
          })}
        >
          ＋ {quickList.name}
        </button>
      )}
      {canEdit && !selecting && t.status !== "done" && (
        <ListAdd allotmentId={id} taskIds={[t.id!]} label={`Add ${t.title} to a list`} except={listsOf(t.id!).map((l) => l.id!)} onAdded={listAdded} onError={setError} />
      )}
      {canEdit && !selecting && t.status !== "done" && (
        <select className="reschedule" aria-label={`Reschedule ${t.title}`} value="" onChange={(e) => reschedule(t, e.target.value)}>
          <option value="">📅</option>
          <option value="tomorrow">Tomorrow</option>
          <option value="week">Next week</option>
          <option value="none">No date</option>
        </select>
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

  const open = groups.overdue.length + groups.today.length + groups.upcoming.length + groups.undated.length;
  const filtered = isFiltered(filters);
  const doneVisible = showDone || filters.status === "done";

  return (
    <main className="page wide">
      <h1>Tasks</h1>
      {canEdit ? (
        <p className="toolbar">
          <button type="button" onClick={() => setDialog("new")}>+ New task</button>
          <button type="button" className="secondary" aria-pressed={selecting} onClick={() => (selecting ? leaveSelecting() : setSelecting(true))}>
            {selecting ? "Done selecting" : "Select"}
          </button>
        </p>
      ) : (
        <p className="muted">View only: ask an owner for editor access to add or complete tasks.</p>
      )}

      <div className="toolbar filters" role="search">
        <input type="search" aria-label="Search tasks" placeholder="Search tasks" value={filters.q} onChange={(e) => change({ q: e.target.value })} />
        <select aria-label="Assigned to" value={filters.who} onChange={(e) => change({ who: e.target.value })}>
          <option value="all">Everyone</option>
          <option value="me">Mine</option>
          <option value="none">Unassigned</option>
          {members.data?.map((m) => <option key={m.user_id} value={String(m.user_id)}>{m.display_name}</option>)}
        </select>
        <select aria-label="Priority" value={filters.priority} onChange={(e) => change({ priority: e.target.value as Filters["priority"] })}>
          <option value="">Any priority</option>
          <option value="high">High</option>
          <option value="normal">Normal</option>
          <option value="low">Low</option>
        </select>
        <select aria-label="Status" value={filters.status} onChange={(e) => change({ status: e.target.value as Filters["status"] })}>
          <option value="all">Any status</option>
          <option value="todo">To do</option>
          <option value="doing">Doing</option>
          <option value="done">Done</option>
        </select>
        <select aria-label="Place" value={filters.place} onChange={(e) => change({ place: e.target.value })}>
          <option value="">Anywhere</option>
          <PlaceOptions features={features.data} trays={trays.data} plantings={plantings.data} />
        </select>
        <select aria-label="Sort by" value={filters.sort} onChange={(e) => change({ sort: e.target.value as Filters["sort"] })}>
          <option value="due">Sort: due date</option>
          <option value="priority">Sort: priority</option>
          <option value="newest">Sort: newest</option>
        </select>
        {filtered && (
          <button type="button" className="link" onClick={() => setParams(writeFilters({ ...DEFAULT_FILTERS, sort: filters.sort }, params), { replace: true })}>
            Clear filters
          </button>
        )}
      </div>

      {selecting && (
        <div className="toolbar bulk-bar" role="group" aria-label="Selected tasks">
          <strong>{picked.size} selected</strong>
          <button type="button" disabled={picked.size === 0 || actions.bulk.isPending} onClick={() => bulk("complete")}>Complete</button>
          <button type="button" className="secondary" disabled={picked.size === 0 || actions.bulk.isPending} onClick={() => bulk("reschedule", dates.tomorrow)}>Tomorrow</button>
          <button type="button" className="secondary" disabled={picked.size === 0 || actions.bulk.isPending} onClick={() => bulk("reschedule", dates.nextWeek)}>Next week</button>
          <button type="button" className="secondary" disabled={picked.size === 0 || actions.bulk.isPending} onClick={() => bulk("reschedule", null)}>No date</button>
          <ListAdd
            allotmentId={id}
            mode="bulk"
            taskIds={[...picked]}
            label="Day list for the selected tasks"
            placeholder="Choose a list…"
            onAdded={(listId, name, count) => {
              listAdded(listId, name, count);
              leaveSelecting();
            }}
            onError={setError}
          />
          {!confirmDelete ? (
            <button type="button" className="danger" disabled={picked.size === 0} onClick={() => setConfirmDelete(true)}>Delete</button>
          ) : (
            <>
              <span className="muted">Delete {picked.size} task{picked.size === 1 ? "" : "s"}?</span>
              <button type="button" className="danger" disabled={actions.bulk.isPending} onClick={() => bulk("delete")}>Yes, delete</button>
              <button type="button" className="secondary" onClick={() => setConfirmDelete(false)}>No</button>
            </>
          )}
        </div>
      )}
      {error && <p role="alert" className="error">{error}</p>}
      {added && (
        <p role="status" className="ok">
          Added {added.count} task{added.count === 1 ? "" : "s"} to {added.name}. <Link to={`../today?list=${added.listId}`}>Open the sheet</Link>
        </p>
      )}

      {tasks.isLoading && <p className="muted">Loading…</p>}
      {tasks.data && open === 0 && filters.status !== "done" && (
        <p className="muted">{filtered ? "No tasks match those filters." : "Nothing to do. Enjoy the sunshine ☀️"}</p>
      )}
      {filters.sort === "due" ? (
        <>
          {section("Overdue", groups.overdue, "overdue")}
          {section("Today", groups.today)}
          {section("Upcoming", groups.upcoming)}
          {section("No date", groups.undated)}
        </>
      ) : (
        section("Open", shown.filter((t) => t.status !== "done"))
      )}
      {groups.done.length > 0 && filters.status !== "done" && (
        <p><button className="link" onClick={() => setShowDone(!showDone)}>{showDone ? "Hide" : "Show"} completed ({groups.done.length})</button></p>
      )}
      {doneVisible && section("Completed", groups.done)}
      {dialog && (
        <TaskDialog allotmentId={id} canEdit={canEdit} meId={user?.id} isOwner={allotment.role === "owner"} task={dialog === "new" ? undefined : dialog} onClose={() => setDialog(null)} />
      )}
    </main>
  );
}
