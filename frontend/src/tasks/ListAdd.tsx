import { useState } from "react";
import DayListsDialog from "./DayListsDialog";
import { useDayListActions, useDayLists, useSelectedList } from "./dayLists";

type Props = {
  allotmentId: number;
  taskIds: number[];
  /** "menu": choosing a list adds at once. "bulk": choose, then press Add. */
  mode?: "menu" | "bulk";
  label: string;
  placeholder?: string;
  disabled?: boolean;
  /** Lists the tasks are already on, left out of the choices. */
  except?: number[];
  onAdded?(listId: number, listName: string, count: number): void;
  onError?(message: string): void;
};

/** Add tasks to a day list: a list picker with "New list…" (which makes the list, then adds to it). */
export default function ListAdd({ allotmentId, taskIds, mode = "menu", label, placeholder = "📋", disabled, except = [], onAdded, onError }: Props) {
  const lists = useDayLists(allotmentId);
  const actions = useDayListActions(allotmentId);
  const [selected, select] = useSelectedList(allotmentId);
  const [making, setMaking] = useState<number[] | null>(null);
  const [choice, setChoice] = useState("");

  const all = lists.data ?? [];
  const current = all.find((l) => l.id === selected) ?? null;
  const choices = all.filter((l) => !except.includes(l.id!));

  async function add(listId: number, ids: number[]) {
    try {
      const list = await actions.addTasks.mutateAsync({ id: listId, taskIds: ids });
      select(listId);
      onAdded?.(listId, list.name ?? "", ids.length);
    } catch (err) {
      onError?.((err as Error).message);
    }
  }

  function pick(value: string) {
    if (value === "new") return setMaking(taskIds);
    if (mode === "bulk") return setChoice(value);
    if (value) void add(Number(value), taskIds);
  }

  return (
    <>
      <select
        className="reschedule"
        aria-label={label}
        value={mode === "bulk" ? choice || (current ? String(current.id) : "") : ""}
        disabled={disabled}
        onChange={(e) => pick(e.target.value)}
      >
        <option value="">{placeholder}</option>
        {choices.map((l) => (
          <option key={l.id} value={l.id}>{l.id === current?.id ? `★ ${l.name}` : l.name}</option>
        ))}
        <option value="new">New list…</option>
      </select>
      {mode === "bulk" && (
        <button
          type="button"
          className="secondary"
          disabled={disabled || taskIds.length === 0 || actions.addTasks.isPending || !(choice || current)}
          onClick={() => void add(Number(choice || current!.id), taskIds)}
        >
          Add to list
        </button>
      )}
      {making && (
        <DayListsDialog
          allotmentId={allotmentId}
          canEdit
          onClose={() => setMaking(null)}
          onCreated={(made) => {
            select(made.id!);
            if (making.length > 0) void add(made.id!, making);
            setMaking(null);
          }}
        />
      )}
    </>
  );
}
