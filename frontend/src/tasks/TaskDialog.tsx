import { useState } from "react";
import Modal from "../components/Modal";
import PlaceOptions from "./PlaceOptions";
import { usePlantings } from "../plantings/hooks";
import { useTrays } from "../trays/hooks";
import type { Task } from "./group";
import { useDayListActions, useDayLists } from "./dayLists";
import { useFeatureOptions, useMembers, useTaskActions, type NewTask } from "./hooks";
import ListAdd from "./ListAdd";
import TaskComments from "./TaskComments";

const PRIORITIES = ["low", "normal", "high"] as const;
const RECURRENCES = ["daily", "weekly", "monthly"] as const;

export type Place = { feature_id?: number | null; tray_id?: number | null; planting_id?: number | null };

/** One place per task, held in a single select as "feature:3", "tray:2" or "planting:7". */
export const placeValue = (p: Place): string =>
  p.feature_id ? `feature:${p.feature_id}` : p.tray_id ? `tray:${p.tray_id}` : p.planting_id ? `planting:${p.planting_id}` : "";

export function placeFromValue(value: string): Required<Place> {
  const [kind, id] = value.split(":");
  return {
    feature_id: kind === "feature" ? Number(id) : null,
    tray_id: kind === "tray" ? Number(id) : null,
    planting_id: kind === "planting" ? Number(id) : null,
  };
}

type Props = {
  allotmentId: number;
  canEdit: boolean;
  /** The task to edit; leave out to make a new one. */
  task?: Task;
  /** Where a new task starts out (e.g. the bed selected on the map). */
  place?: Place;
  /** The signed-in user and whether they own the allotment: who may edit or delete a comment. */
  meId?: number;
  isOwner?: boolean;
  onClose(): void;
};

export default function TaskDialog({ allotmentId, canEdit, task, place, meId, isOwner, onClose }: Props) {
  const features = useFeatureOptions(allotmentId);
  const trays = useTrays(allotmentId);
  const plantings = usePlantings(allotmentId, { growing: true });
  const members = useMembers(allotmentId);
  const actions = useTaskActions(allotmentId);
  const dayLists = useDayLists(allotmentId);
  const listActions = useDayListActions(allotmentId);
  const onLists = (dayLists.data ?? []).filter((l) => task?.id != null && l.task_ids?.includes(task.id));
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  // A select only takes its default when it is created, so those fed by a query are re-made once it arrives.
  const editing = task !== undefined;
  const done = task?.status === "done";
  const readOnly = !canEdit;
  const busy = actions.create.isPending || actions.update.isPending || actions.remove.isPending;

  async function save(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const text = (k: string) => String(f.get(k) ?? "");
    const body = {
      title: text("title").trim(),
      description: text("description"),
      due_date: text("due_date") || null,
      priority: text("priority") as (typeof PRIORITIES)[number],
      recurrence: (text("recurrence") || null) as (typeof RECURRENCES)[number] | null,
      assignee_id: text("assignee_id") ? Number(text("assignee_id")) : null,
      ...placeFromValue(text("place")),
    };
    try {
      if (editing) {
        await actions.update.mutateAsync({ id: task.id!, body: done ? body : { ...body, status: text("status") as "todo" | "doing" } });
      } else {
        await actions.create.mutateAsync({ ...body, status: text("status") as "todo" | "doing" } as NewTask);
      }
      onClose();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function remove() {
    try {
      await actions.remove.mutateAsync(task!.id!);
      onClose();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  const who = (id?: number | null) => members.data?.find((m) => m.user_id === id)?.display_name ?? "someone";
  const start = task ? placeValue(task) : place ? placeValue(place) : "";

  return (
    <Modal title={editing ? "Edit task" : "New task"} onClose={onClose}>
      <form className="task-dialog" onSubmit={save}>
        <label>
          Title
          <input name="title" defaultValue={task?.title ?? ""} required maxLength={200} disabled={readOnly} autoFocus={!editing} />
        </label>
        <label>
          Notes
          <textarea name="description" rows={3} defaultValue={task?.description ?? ""} disabled={readOnly} />
        </label>
        <div className="pair">
          <label>
            Due date
            <input name="due_date" type="date" defaultValue={task?.due_date ?? ""} disabled={readOnly} />
          </label>
          <label>
            Priority
            <select name="priority" defaultValue={task?.priority ?? "normal"} disabled={readOnly}>
              {PRIORITIES.map((p) => <option key={p}>{p}</option>)}
            </select>
          </label>
        </div>
        <div className="pair">
          <label>
            Status
            <select name="status" defaultValue={done ? "done" : (task?.status ?? "todo")} disabled={readOnly || done}>
              <option value="todo">To do</option>
              <option value="doing">Doing</option>
              {done && <option value="done">Done</option>}
            </select>
          </label>
          <label>
            Assigned to
            <select key={String(!!members.data)} name="assignee_id" defaultValue={task?.assignee_id ?? ""} disabled={readOnly}>
              <option value="">Nobody</option>
              {members.data?.map((m) => <option key={m.user_id} value={m.user_id}>{m.display_name}</option>)}
            </select>
          </label>
        </div>
        <div className="pair">
          <label>
            Where
            <select key={`${!!features.data}${!!trays.data}${!!plantings.data}`} name="place" defaultValue={start} disabled={readOnly}>
              <option value="">Nowhere in particular</option>
              <PlaceOptions features={features.data} trays={trays.data} plantings={plantings.data} />
            </select>
          </label>
          <label>
            Repeats
            <select name="recurrence" defaultValue={task?.recurrence ?? ""} disabled={readOnly}>
              <option value="">Doesn't repeat</option>
              {RECURRENCES.map((r) => <option key={r}>{r}</option>)}
            </select>
          </label>
        </div>
        {editing && task?.id != null && (onLists.length > 0 || canEdit) && (
          <div className="task-lists">
            <span>Day lists</span>
            {onLists.length === 0 && <span className="muted">not on any list</span>}
            {onLists.map((l) => (
              <span key={l.id} className="badge on-list">
                📋 {l.name}
                {canEdit && (
                  <button
                    type="button"
                    className="link"
                    aria-label={`Take this task off ${l.name}`}
                    onClick={() => listActions.removeTask.mutate({ id: l.id!, taskId: task.id! }, { onError: (err) => setError((err as Error).message) })}
                  >
                    ✕
                  </button>
                )}
              </span>
            ))}
            {canEdit && (
              <ListAdd allotmentId={allotmentId} taskIds={[task.id]} label="Add this task to a list" placeholder="Add to a list…" except={onLists.map((l) => l.id!)} onError={setError} />
            )}
          </div>
        )}
        {done && task?.completed_at && (
          <p className="done-note">
            Done by {who(task.completed_by)} on {new Date(task.completed_at).toLocaleDateString("en-GB")}.
          </p>
        )}
        {error && <p role="alert" className="error">{error}</p>}
        <div className="actions">
          {canEdit && <button type="submit" disabled={busy}>{editing ? "Save" : "Add task"}</button>}
          <button type="button" className="secondary" onClick={onClose}>{canEdit ? "Cancel" : "Close"}</button>
          <span className="spacer" />
          {canEdit && editing && !confirmDelete && (
            <button type="button" className="danger" onClick={() => setConfirmDelete(true)}>Delete</button>
          )}
          {canEdit && editing && confirmDelete && (
            <>
              <span className="muted">Delete this task?</span>
              <button type="button" className="danger" disabled={busy} onClick={remove}>Yes, delete</button>
              <button type="button" className="secondary" onClick={() => setConfirmDelete(false)}>No</button>
            </>
          )}
        </div>
      </form>
      {editing && task?.id != null && (
        <TaskComments allotmentId={allotmentId} taskId={task.id} canEdit={canEdit} meId={meId} isOwner={isOwner} />
      )}
    </Modal>
  );
}
