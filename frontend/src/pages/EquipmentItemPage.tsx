import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { STATUS_LABEL, useEquipmentActions, useEquipmentItem, useEquipmentKinds, type EquipmentStatus, type KindKey } from "../equipment/hooks";
import { useFeatureOptions } from "../tasks/hooks";
import { useAllotment } from "./AllotmentLayout";

const day = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });

export default function EquipmentItemPage() {
  const { id, canEdit } = useAllotment();
  const equipmentId = Number(useParams().equipmentId);
  const navigate = useNavigate();
  const item = useEquipmentItem(id, equipmentId);
  const kinds = useEquipmentKinds();
  const features = useFeatureOptions(id);
  const actions = useEquipmentActions(id);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const e = item.data;
  if (item.isLoading) return <main className="page"><p className="muted">Loading…</p></main>;
  if (!e) return <main className="page"><p>Equipment not found. <Link to="../equipment">Back to equipment</Link></p></main>;

  async function save(ev: React.FormEvent<HTMLFormElement>) {
    ev.preventDefault();
    const f = new FormData(ev.currentTarget);
    const text = (k: string) => String(f.get(k) ?? "").trim();
    try {
      await actions.patch.mutateAsync({
        id: equipmentId,
        name: text("name"),
        kind: (text("kind") || null) as KindKey | null,
        quantity: Number(text("quantity")) || 1,
        status: text("status") as EquipmentStatus,
        location_feature_id: text("location") ? Number(text("location")) : null,
        used_for: text("used_for"),
        notes: text("notes"),
      });
      setError(null);
      setNotice("Saved");
    } catch (err) {
      setNotice(null);
      setError((err as Error).message);
    }
  }

  async function remove() {
    try {
      await actions.remove.mutateAsync(equipmentId);
      navigate("../equipment");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  // A select only takes its default when it is made, so the ones fed by a query are re-made once it arrives.
  return (
    <main className="page">
      <p><Link to="../equipment">← All equipment</Link></p>
      <h1>{e.name}</h1>
      {e.status === "out_of_action" && <p className="badge out-of-action">Out of action</p>}
      <form className="equipment-form" key={e.updated_at} onSubmit={(ev) => void save(ev)}>
        <fieldset disabled={!canEdit}>
          <label>
            Name
            <input name="name" defaultValue={e.name} required maxLength={120} />
          </label>
          <div className="pair">
            <label>
              Kind
              <select key={String(!!kinds.data)} name="kind" defaultValue={e.kind ?? ""}>
                <option value="">Other</option>
                {(kinds.data ?? []).map((k) => (
                  <option key={k.key} value={k.key}>
                    {k.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              How many
              <input name="quantity" type="number" min={1} defaultValue={e.quantity} />
            </label>
          </div>
          <div className="pair">
            <label>
              Status
              <select name="status" defaultValue={e.status}>
                <option value="in_service">{STATUS_LABEL.in_service}</option>
                <option value="out_of_action">{STATUS_LABEL.out_of_action}</option>
              </select>
            </label>
            <label>
              Kept in
              <select key={String(!!features.data)} name="location" defaultValue={e.location_feature_id ?? ""}>
                <option value="">Nowhere in particular</option>
                {(features.data ?? []).map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <label>
            Used for
            <textarea name="used_for" rows={2} defaultValue={e.used_for} maxLength={1000} placeholder="dig, double digging, turning compost" />
            <span className="hint">Words that make this suggested for a task, separated by commas. Leave blank to rely on its kind.</span>
          </label>
          <label>
            Notes
            <textarea name="notes" rows={3} defaultValue={e.notes} maxLength={5000} />
          </label>
        </fieldset>
        {e.last_serviced_on && <p className="muted">Last serviced {day(e.last_serviced_on)}.</p>}
        {canEdit && (
          <p className="actions">
            <button type="submit" disabled={actions.patch.isPending}>Save</button>
            {notice && <span role="status" className="ok"> {notice}</span>}
          </p>
        )}
        {error && <p role="alert" className="error">{error}</p>}
      </form>

      {canEdit && (
        <section className="danger-zone">
          {confirmDelete ? (
            <button type="button" className="danger" onClick={() => void remove()}>Really delete this?</button>
          ) : (
            <button type="button" className="secondary" onClick={() => setConfirmDelete(true)}>Delete</button>
          )}
        </section>
      )}
    </main>
  );
}
