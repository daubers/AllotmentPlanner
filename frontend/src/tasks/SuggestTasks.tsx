import { useState } from "react";
import Modal from "../components/Modal";
import { useSuggestedTasks, type SuggestFor } from "./hooks";

/** A "Suggest tasks" button: lists the jobs the seed packets' dates suggest and adds them all at once. */
export default function SuggestTasks({ allotmentId, target }: { allotmentId: number; target: SuggestFor }) {
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [added, setAdded] = useState<number | null>(null);
  const { suggestions, add } = useSuggestedTasks(allotmentId, target, open);
  const list = suggestions.data ?? [];
  const fresh = list.filter((s) => !s.added);

  const close = () => {
    setOpen(false);
    setError(null);
    setAdded(null);
  };
  async function addAll() {
    try {
      setAdded((await add.mutateAsync()).length);
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
