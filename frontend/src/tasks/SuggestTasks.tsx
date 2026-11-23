import { useState } from "react";
import Modal from "../components/Modal";
import ToolTicks from "../equipment/ToolTicks";
import { useSuggestedTasks, type SuggestFor } from "./hooks";

/** A "Suggest tasks" button: lists the jobs the seed packets' dates suggest and adds them all at once. */
export default function SuggestTasks({ allotmentId, target }: { allotmentId: number; target: SuggestFor }) {
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [added, setAdded] = useState<number | null>(null);
  const [unticked, setUnticked] = useState<Set<string>>(new Set()); // "key:equipmentId" the user switched off
  const { suggestions, add } = useSuggestedTasks(allotmentId, target, open);
  const list = suggestions.data ?? [];
  const fresh = list.filter((s) => !s.added);

  const close = () => {
    setOpen(false);
    setError(null);
    setAdded(null);
  };
  const flip = (key: string, id: number) =>
    setUnticked((prev) => {
      const next = new Set(prev);
      const k = `${key}:${id}`;
      if (next.has(k)) next.delete(k);
      else next.add(k);
      return next;
    });
  /** Each new task gets the equipment still ticked on its row. */
  const chosen = () =>
    Object.fromEntries(
      fresh
        .map((s) => [s.key!, (s.equipment ?? []).filter((e) => !unticked.has(`${s.key}:${e.id}`)).map((e) => e.id!)] as const)
        .filter(([, ids]) => ids.length > 0),
    );
  async function addAll() {
    try {
      const equipment = chosen();
      setAdded((await add.mutateAsync(Object.keys(equipment).length ? equipment : undefined)).length);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <>
      <button type="button" className="secondary" onClick={() => setOpen(true)}>Suggest tasks</button>
      {open && (
        <Modal title="Suggested tasks" onClose={close}>
          {suggestions.isLoading && <p className="muted">Working it out…</p>}
          {suggestions.data && list.length === 0 && (
            <p className="muted">
              Nothing to suggest. Suggestions need seeds sown with a date, and skip steps whose date has already passed.
            </p>
          )}
          {list.length > 0 && (
            <ul className="suggested-tasks">
              {list.map((s) => (
                <li key={s.key}>
                  <strong>{s.title}</strong>
                  <span className="muted"> · {s.due_date}{s.added ? " · already added" : ""}</span>
                  <span className="muted block">{s.description}</span>
                  {!s.added && (
                    <ToolTicks
                      items={s.equipment ?? []}
                      unticked={new Set((s.equipment ?? []).filter((e) => unticked.has(`${s.key}:${e.id}`)).map((e) => e.id!))}
                      onToggle={(id) => flip(s.key!, id)}
                    />
                  )}
                </li>
              ))}
            </ul>
          )}
          {added !== null && <p role="status">Added {added} task{added === 1 ? "" : "s"}. You will find them on the Tasks and Today pages.</p>}
          {error && <p role="alert" className="error">{error}</p>}
          <div className="inline">
            {added === null && fresh.length > 0 && (
              <button type="button" disabled={add.isPending} onClick={() => void addAll()}>
                Add {fresh.length === list.length ? "all" : "the other"} {fresh.length} task{fresh.length === 1 ? "" : "s"}
              </button>
            )}
            <button type="button" className="secondary" onClick={close}>{added === null ? "Cancel" : "Close"}</button>
          </div>
        </Modal>
      )}
    </>
  );
}
