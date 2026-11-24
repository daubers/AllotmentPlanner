import { useState } from "react";
import Modal from "../components/Modal";
import { addDays, todayISO } from "../plan/dates";
import { dayLabel } from "../plan/window";
import { useFeatureOptions } from "../tasks/hooks";
import { bookingConflicts, involving } from "./conflicts";
import { useBookingActions, useBookings, useEquipmentList } from "./hooks";

export type BookingTarget = { kind: "feature" | "planting"; id: number; label: string };

/** Put some equipment to use on a bed or planting for a stretch of time; warns if that is more than you own. */
export default function BookEquipmentDialog({
  allotmentId,
  equipmentId,
  target,
  onClose,
}: {
  allotmentId: number;
  /** The item, if already chosen (from its own page). */
  equipmentId?: number;
  /** The bed or planting, if already chosen (from a bed page). */
  target?: BookingTarget;
  onClose(): void;
}) {
  const equipment = useEquipmentList(allotmentId);
  const features = useFeatureOptions(allotmentId);
  const actions = useBookingActions(allotmentId);
  const [chosen, setChosen] = useState<number | "">(equipmentId ?? "");
  const [bed, setBed] = useState<number | "">("");
  const [quantity, setQuantity] = useState("1");
  const [starts, setStarts] = useState(todayISO());
  const [ends, setEnds] = useState(addDays(todayISO(), 30));
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);

  const item = equipment.data?.find((e) => e.id === chosen);
  const existing = useBookings(allotmentId, { equipmentId: Number(chosen) }, chosen !== "");
  const draft = { id: 0, quantity: Number(quantity) || 1, starts_on: starts, ends_on: ends };
  const clashes =
    item && ends > starts
      ? involving(bookingConflicts([...(existing.data ?? []).map((b) => ({ id: b.id!, quantity: b.quantity!, starts_on: b.starts_on!, ends_on: b.ends_on! })), draft], item.quantity ?? 1), 0)
      : [];
  const beds = (features.data ?? []).filter((f) => f.kind === "bed");

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    if (chosen === "") return setError("Choose the equipment.");
    const where = target ?? (bed !== "" ? { kind: "feature" as const, id: Number(bed) } : null);
    if (!where) return setError("Choose a bed.");
    try {
      await actions.create.mutateAsync({
        equipmentId: Number(chosen),
        body: {
          feature_id: where.kind === "feature" ? where.id : null,
          planting_id: where.kind === "planting" ? where.id : null,
          starts_on: starts,
          ends_on: ends,
          quantity: draft.quantity,
          note: note.trim(),
        },
      });
      onClose();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <Modal title={target ? `Put equipment to use on ${target.label}` : "Put equipment to use"} onClose={onClose}>
      <form className="task-dialog" onSubmit={submit}>
        {equipmentId === undefined && (
          <label>
            Equipment
            <select value={chosen} onChange={(e) => setChosen(e.target.value ? Number(e.target.value) : "")}>
              <option value="">Choose…</option>
              {(equipment.data ?? []).filter((e) => e.status !== "out_of_action").map((e) => (
                <option key={e.id} value={e.id}>
                  {e.name}
                  {(e.quantity ?? 1) > 1 ? ` (you have ${e.quantity})` : ""}
                </option>
              ))}
            </select>
          </label>
        )}
        {!target && (
          <label>
            Bed
            <select value={bed} onChange={(e) => setBed(e.target.value ? Number(e.target.value) : "")}>
              <option value="">Choose…</option>
              {beds.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name}
                </option>
              ))}
            </select>
          </label>
        )}
        <label>
          How many
          <input type="number" min={1} value={quantity} onChange={(e) => setQuantity(e.target.value)} />
        </label>
        <div className="pair">
          <label>
            From
            <input type="date" value={starts} onChange={(e) => setStarts(e.target.value)} required />
          </label>
          <label>
            Until (the day it is free again)
            <input type="date" value={ends} onChange={(e) => setEnds(e.target.value)} required />
          </label>
        </div>
        <label>
          Note
          <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} placeholder="optional" />
        </label>
        {clashes.length > 0 && item && (
          <p role="status" className="plan-stale">
            You only have {item.quantity} {item.name}: {clashes[0].used} would be in use from {dayLabel(clashes[0].from)} to {dayLabel(clashes[0].to)}.
            You can still save it.
          </p>
        )}
        {error && <p role="alert" className="error">{error}</p>}
        <div className="actions">
          <button type="submit" disabled={actions.create.isPending}>Put to use</button>
          <button type="button" className="secondary" onClick={onClose}>Cancel</button>
        </div>
      </form>
    </Modal>
  );
}
