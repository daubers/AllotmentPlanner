import type { EquipmentSuggestion } from "./hooks";

/** The equipment suggested for a generated task, each with a tick (ticked means it will go on the task). */
export default function ToolTicks({
  items,
  unticked,
  onToggle,
  disabled = false,
}: {
  items: EquipmentSuggestion[];
  /** Ids of the items the user has switched off. */
  unticked: Set<number>;
  onToggle(id: number): void;
  disabled?: boolean;
}) {
  if (items.length === 0) return null;
  return (
    <span className="tool-ticks" role="group" aria-label="Equipment to add">
      <span className="muted">🔧</span>
      {items.map((e) => (
        <label key={e.id} className="tool-tick" title={e.reason ? `Suggested for ${e.reason}` : undefined}>
          <input type="checkbox" checked={!unticked.has(e.id!)} onChange={() => onToggle(e.id!)} disabled={disabled} />
          {e.name}
        </label>
      ))}
    </span>
  );
}
