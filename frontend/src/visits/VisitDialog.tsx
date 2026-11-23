import { useState } from "react";
import Modal from "../components/Modal";
import EquipmentChips from "../equipment/EquipmentChips";
import { useEquipmentList } from "../equipment/hooks";
import { useTasks } from "../tasks/hooks";
import { addTool, extrasOf, previewBring, removeTool, type Extras } from "./bring";
import { useVisitActions, type Visit } from "./hooks";

/** YYYY-MM-DD and HH:MM in the browser's local timezone, for the date/time inputs. */
function toLocalInputs(iso: string): { date: string; time: string } {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return {
    date: `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`,
    time: `${pad(d.getHours())}:${pad(d.getMinutes())}`,
  };
}

/** Local date + time inputs, interpreted in the browser's timezone, as a UTC ISO instant. */
function fromLocalInputs(date: string, time: string): string {
  return new Date(`${date}T${time || "09:00"}`).toISOString();
}

export default function VisitDialog({
  allotmentId,
  visit,
  onClose,
}: {
  allotmentId: number;
  /** Editing an existing visit, or "new". */
  visit: Visit | "new";
  onClose(): void;
}) {
  const tasks = useTasks(allotmentId);
  const actions = useVisitActions(allotmentId);
  const editing = visit !== "new" ? visit : null;
  const initial = editing ? toLocalInputs(editing.starts_at!) : toLocalInputs(new Date().toISOString());
  const [picked, setPicked] = useState<Set<number>>(new Set(editing?.task_ids ?? []));
  const [error, setError] = useState<string | null>(null);
  const [extras, setExtras] = useState<Extras>(extrasOf(editing ?? undefined));
  const equipment = useEquipmentList(allotmentId);

  const open = (tasks.data ?? []).filter((t) => t.status !== "done");
  const known = (id: number) => {
    const e = equipment.data?.find((x) => x.id === id);
    return e ? { name: e.name!, outOfAction: e.status === "out_of_action" } : undefined;
  };
  const pickedTasks = (tasks.data ?? []).filter((t) => picked.has(t.id!));
  const bring = previewBring(pickedTasks, editing?.bring, extras, known);
  const listed = bring.map((b) => b.id);
  // Equipment a picked job already needs: putting it back on the list just stops hiding it.
  const needed = new Set(pickedTasks.filter((t) => t.status !== "done").flatMap((t) => (t.equipment ?? []).map((e) => e.id!)));

  /** The chips control reports the whole new list; turn the difference into add/remove. */
  function changeBring(next: number[]) {
    let out = extras;
    for (const id of listed.filter((x) => !next.includes(x))) out = removeTool(out, id);
    for (const id of next.filter((x) => !listed.includes(x))) out = addTool(out, id, needed.has(id));
    setExtras(out);
  }

  function toggle(id: number) {
    setPicked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const title = String(f.get("title") ?? "").trim();
    const date = String(f.get("date") ?? "");
    const time = String(f.get("time") ?? "");
    const duration_minutes = Number(f.get("duration_minutes") ?? 120);
    const notes = String(f.get("notes") ?? "").trim();
    if (!title || !date) return;
    const starts_at = fromLocalInputs(date, time);
    try {
      if (editing) {
        await actions.update.mutateAsync({
          id: editing.id!,
          body: { title, starts_at, duration_minutes, notes, equipment_adds: extras.adds, equipment_removes: extras.removes },
        });
        const before = new Set(editing.task_ids ?? []);
        const toAdd = [...picked].filter((id) => !before.has(id));
        const toRemove = [...before].filter((id) => !picked.has(id));
        if (toAdd.length) await actions.addTasks.mutateAsync({ id: editing.id!, taskIds: toAdd });
        for (const taskId of toRemove) {
          await actions.removeTask.mutateAsync({ id: editing.id!, taskId });
        }
      } else {
        await actions.create.mutateAsync({
          title,
          starts_at,
          duration_minutes,
          notes,
          task_ids: [...picked],
          equipment_adds: extras.adds,
          equipment_removes: extras.removes,
        });
      }
      onClose();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  const pending = actions.create.isPending || actions.update.isPending;

  return (
    <Modal title={editing ? "Edit visit" : "Plan a visit"} onClose={onClose}>
      <form className="visit-form" onSubmit={(e) => void submit(e)}>
        <label>
          Title
          <input name="title" defaultValue={editing?.title ?? ""} maxLength={200} required autoFocus />
        </label>
        <div className="inline">
          <label>
            Date
            <input name="date" type="date" defaultValue={initial.date} required />
          </label>
          <label>
            Time
            <input name="time" type="time" defaultValue={initial.time} />
          </label>
          <label>
            Minutes
            <input name="duration_minutes" type="number" min={1} max={1440} defaultValue={editing?.duration_minutes ?? 120} />
          </label>
        </div>
        <label>
          Notes
          <textarea name="notes" defaultValue={editing?.notes ?? ""} maxLength={5000} rows={3} />
        </label>
        <fieldset className="visit-tasks">
          <legend>Tasks to bring</legend>
          {tasks.isLoading && <p className="muted">Loading…</p>}
          {open.length === 0 && !tasks.isLoading && <p className="muted">No open jobs to pick from.</p>}
          <ul>
            {open.map((t) => (
              <li key={t.id}>
                <label className="check">
                  <input type="checkbox" checked={picked.has(t.id!)} onChange={() => toggle(t.id!)} />
                  {t.title}
                </label>
              </li>
            ))}
          </ul>
        </fieldset>
        <fieldset className="visit-bring">
          <legend>Equipment to bring</legend>
          <EquipmentChips allotmentId={allotmentId} value={listed} onChange={changeBring} known={bring.map((b) => ({ id: b.id, name: b.name, status: b.outOfAction ? "out_of_action" : "in_service" }))} />
          <p className="hint">What the jobs above need. Tools suggested for a job appear once the visit is saved; add or remove any here.</p>
        </fieldset>
        {error && <p role="alert" className="error">{error}</p>}
        <button type="submit" disabled={pending}>{editing ? "Save" : "Plan visit"}</button>
      </form>
    </Modal>
  );
}
