import { useState } from "react";
import { dayLabel } from "../plan/window";
import BookEquipmentDialog, { type BookingTarget } from "./BookEquipmentDialog";
import { useBookingActions, type Booking } from "./hooks";

const when = (b: Booking) => `${dayLabel(b.starts_on!)} to ${dayLabel(b.ends_on!)}`;

/** A list of equipment bookings with a way to remove one and (optionally) to add one. */
export default function InUse({
  allotmentId,
  title,
  bookings,
  canEdit,
  show,
  add,
}: {
  allotmentId: number;
  title: string;
  bookings: Booking[];
  canEdit: boolean;
  /** What to name each booking by: the equipment (on a bed) or where it is (on an item). */
  show: "equipment" | "where";
  /** If given, an "Put equipment to use" button that books onto this bed or planting. */
  add?: { equipmentId?: number; target?: BookingTarget };
}) {
  const actions = useBookingActions(allotmentId);
  const [booking, setBooking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function remove(id: number) {
    try {
      await actions.remove.mutateAsync(id);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <section className="in-use" aria-label={title}>
      <h2>{title}</h2>
      {bookings.length === 0 ? (
        <p className="muted">Nothing in use.</p>
      ) : (
        <ul className="maintenance-list">
          {bookings.map((b) => (
            <li key={b.id}>
              <span>
                <strong>{show === "equipment" ? b.equipment_name : (b.feature_name ?? b.planting_label)}</strong>
                {(b.quantity ?? 1) > 1 && <> × {b.quantity}</>} <span className="muted">{when(b)}</span>
                {b.note && <span className="muted"> · {b.note}</span>}
              </span>
              {canEdit && (
                <button type="button" className="link" aria-label={`Stop using ${show === "equipment" ? b.equipment_name : (b.feature_name ?? b.planting_label)} ${when(b)}`} onClick={() => void remove(b.id!)}>
                  ✕
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {error && <p role="alert" className="error">{error}</p>}
      {canEdit && add && (
        <button type="button" className="secondary" onClick={() => setBooking(true)}>
          Put equipment to use
        </button>
      )}
      {booking && add && <BookEquipmentDialog allotmentId={allotmentId} equipmentId={add.equipmentId} target={add.target} onClose={() => setBooking(false)} />}
    </section>
  );
}
