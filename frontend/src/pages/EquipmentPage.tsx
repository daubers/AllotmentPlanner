import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { STATUS_LABEL, useEquipmentActions, useEquipmentKinds, useEquipmentList, type EquipmentStatus, type KindKey } from "../equipment/hooks";
import { useAllotment } from "./AllotmentLayout";

export default function EquipmentPage() {
  const { id, canEdit } = useAllotment();
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [kind, setKind] = useState<KindKey | "">("");
  const [status, setStatus] = useState<EquipmentStatus | "">("");
  const [error, setError] = useState<string | null>(null);
  const kinds = useEquipmentKinds();
  const items = useEquipmentList(id, { q, kind: kind || undefined, status: status || undefined });
  const actions = useEquipmentActions(id);

  async function add(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const text = (k: string) => String(f.get(k) ?? "").trim();
    try {
      const created = await actions.create.mutateAsync({
        name: text("name"),
        kind: (text("kind") || null) as KindKey | null,
        quantity: Number(text("quantity")) || 1,
      });
      navigate(String(created.id));
    } catch (err) {
      setError((err as Error).message);
    }
  }

  const list = items.data ?? [];
  const filtered = !!(q || kind || status);
  return (
    <main className="page wide">
      <h1>Equipment</h1>
      <p className="muted">
        The tools and kit you have: spades, dibbers, cloches. Add what you own and say how many, and it can be suggested for the jobs that
        need it.
      </p>

      {canEdit && (
        <form className="packet-add equipment-add" onSubmit={(e) => void add(e)}>
          <input name="name" placeholder="Name, e.g. Border spade" aria-label="Name" required maxLength={120} />
          <select name="kind" aria-label="Kind" defaultValue="">
            <option value="">Kind of thing…</option>
            {(kinds.data ?? []).map((k) => (
              <option key={k.key} value={k.key}>
                {k.label}
              </option>
            ))}
          </select>
          <input name="quantity" type="number" min={1} defaultValue={1} aria-label="How many" />
          <button type="submit" disabled={actions.create.isPending}>
            Add equipment
          </button>
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
        </form>
      )}

      <div className="packet-filters">
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search equipment" aria-label="Search equipment" />
        <select value={kind} onChange={(e) => setKind(e.target.value as KindKey | "")} aria-label="Kind filter">
          <option value="">Any kind</option>
          {(kinds.data ?? []).map((k) => (
            <option key={k.key} value={k.key}>
              {k.label}
            </option>
          ))}
        </select>
        <select value={status} onChange={(e) => setStatus(e.target.value as EquipmentStatus | "")} aria-label="Status filter">
          <option value="">Any status</option>
          <option value="in_service">{STATUS_LABEL.in_service}</option>
          <option value="out_of_action">{STATUS_LABEL.out_of_action}</option>
        </select>
      </div>

      {items.isLoading ? (
        <p className="muted">Loading…</p>
      ) : list.length === 0 ? (
        <p className="muted">
          {filtered ? "Nothing matches." : canEdit ? "Nothing here yet. Add the first item above." : "Nothing here yet."}
        </p>
      ) : (
        <ul className="packets">
          {list.map((e) => (
            <li key={e.id}>
              <Link to={String(e.id)} className="packet-card">
                <span className="packet-thumb none" aria-hidden="true">
                  🔧
                </span>
                <span className="packet-main">
                  <strong>{e.name}</strong>
                  <span className="muted">{[e.kind ? e.kind_label : null, e.location_name].filter(Boolean).join(" · ")}</span>
                </span>
                {(e.quantity ?? 1) > 1 && <span className="badge">× {e.quantity}</span>}
                {e.overdue && <span className="badge out-of-action">Overdue</span>}
                {e.status === "out_of_action" && <span className="badge out-of-action">Out of action</span>}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
