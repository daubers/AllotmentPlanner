import type { EquipmentSuggestion, TaskEquipment } from "./hooks";
import { useEquipmentList } from "./hooks";

/** The equipment a job needs: chips you can remove, suggested ones you can accept, and a way to add any other. */
export default function EquipmentChips({
  allotmentId,
  value,
  onChange,
  suggestions = [],
  known = [],
  disabled = false,
}: {
  allotmentId: number;
  /** The equipment ids on the job. */
  value: number[];
  onChange(ids: number[]): void;
  suggestions?: EquipmentSuggestion[];
  /** Equipment already on the job (names for ids the list has not loaded yet). */
  known?: TaskEquipment[];
  disabled?: boolean;
}) {
  const all = useEquipmentList(allotmentId).data ?? [];
  const find = (id: number) => all.find((e) => e.id === id) ?? known.find((e) => e.id === id);
  const left = suggestions.filter((s) => !value.includes(s.id!));
  const others = all.filter((e) => !value.includes(e.id!));
  const remove = (id: number) => onChange(value.filter((v) => v !== id));
  const add = (id: number) => onChange([...value, id]);

  return (
    <div className="equipment-chips" role="group" aria-label="Equipment">
      {value.length === 0 && left.length === 0 && <span className="muted">None needed</span>}
      {value.map((id) => {
        const e = find(id);
        const out = e?.status === "out_of_action";
        return (
          <span key={id} className={`chip${out ? " out" : ""}`}>
            🔧 {e?.name ?? "Equipment"}
            {out ? " (out of action)" : ""}
            {!disabled && (
              <button type="button" className="link" aria-label={`Remove ${e?.name ?? "equipment"}`} onClick={() => remove(id)}>
                ✕
              </button>
            )}
          </span>
        );
      })}
      {!disabled &&
        left.map((s) => (
          <button key={s.id} type="button" className="chip suggested" aria-label={`Add ${s.name}`} title={s.reason ? `Suggested for ${s.reason}` : "Suggested"} onClick={() => add(s.id!)}>
            + {s.name}
          </button>
        ))}
      {!disabled && others.length > 0 && (
        <select
          className="chip-add"
          aria-label="Add equipment"
          value=""
          onChange={(e) => e.target.value && add(Number(e.target.value))}
        >
          <option value="">Add equipment…</option>
          {others.map((e) => (
            <option key={e.id} value={e.id}>
              {e.name}
              {e.status === "out_of_action" ? " (out of action)" : ""}
            </option>
          ))}
        </select>
      )}
    </div>
  );
}
