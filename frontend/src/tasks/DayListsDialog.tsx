import { useState } from "react";
import Modal from "../components/Modal";
import { useDayListActions, useDayLists, type DayList } from "./dayLists";

/** Make, rename, date and delete day lists. */
export default function DayListsDialog({ allotmentId, canEdit, onClose, onCreated }: { allotmentId: number; canEdit: boolean; onClose(): void; onCreated?(list: DayList): void }) {
  const lists = useDayLists(allotmentId);
  const actions = useDayListActions(allotmentId);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<number | null>(null);

  async function run(action: () => Promise<unknown>) {
    try {
      await action();
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function create(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    const name = String(f.get("name") ?? "").trim();
    if (!name) return;
    await run(async () => {
      const made = await actions.create.mutateAsync({ name, date: String(f.get("date") ?? "") || null });
      form.reset();
      onCreated?.(made);
    });
  }

  return (
    <Modal title="Day lists" onClose={onClose}>
      {canEdit && (
        <form className="inline daylist-new" onSubmit={(e) => void create(e)} aria-label="New list">
          <input name="name" aria-label="New list name" placeholder="e.g. Saturday morning" maxLength={120} required />
          <input name="date" type="date" aria-label="New list date" />
          <button type="submit" disabled={actions.create.isPending}>Add list</button>
        </form>
      )}
      {lists.isLoading && <p className="muted">Loading…</p>}
      {lists.data?.length === 0 && <p className="muted">No lists yet. Make one, then add jobs to it from the Tasks page or the Today page.</p>}
      <ul className="daylists">
        {(lists.data ?? []).map((l) => (
          <li key={l.id} className="daylist">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const f = new FormData(e.currentTarget);
                const name = String(f.get("name") ?? "").trim();
                if (name) void run(() => actions.update.mutateAsync({ id: l.id!, body: { name, date: String(f.get("date") ?? "") || null } }));
              }}
            >
              <input name="name" aria-label={`Name of ${l.name}`} defaultValue={l.name} disabled={!canEdit} maxLength={120} required />
              <input name="date" type="date" aria-label={`Date of ${l.name}`} defaultValue={l.date ?? ""} disabled={!canEdit} />
              {canEdit && <button type="submit" className="secondary">Save</button>}
            </form>
            <p className="muted">{l.task_count} job{l.task_count === 1 ? "" : "s"}{l.done_count ? `, ${l.done_count} done` : ""}</p>
            {canEdit &&
              (confirming === l.id ? (
                <button type="button" className="danger" onClick={() => void run(() => actions.remove.mutateAsync(l.id!).then(() => setConfirming(null)))}>
                  Really delete {l.name}? The jobs stay.
                </button>
              ) : (
                <button type="button" className="link" onClick={() => setConfirming(l.id!)}>Delete</button>
              ))}
          </li>
        ))}
      </ul>
      {error && <p role="alert" className="error">{error}</p>}
    </Modal>
  );
}
