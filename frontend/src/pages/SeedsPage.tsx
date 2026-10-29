import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import MonthGrid from "../seeds/MonthGrid";
import ScanBox from "../seeds/ScanBox";
import { MONTH_NAMES, STOCK, currentMonth, daysLabel, type StockLevel } from "../seeds/calendar";
import { usePacketActions, usePackets } from "../seeds/hooks";
import { useAllotment } from "./AllotmentLayout";

export default function SeedsPage() {
  const { id, canEdit } = useAllotment();
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [stock, setStock] = useState<StockLevel | "">("");
  const [sowNow, setSowNow] = useState(false);
  const [month, setMonth] = useState(currentMonth());
  const [error, setError] = useState<string | null>(null);
  const packets = usePackets(id, { q, stock: stock || undefined, month: sowNow ? month : undefined, status: "active" });
  const drafts = usePackets(id, { status: "draft" });
  const actions = usePacketActions(id);

  async function add(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const text = (k: string) => String(f.get(k) ?? "").trim();
    try {
      const created = await actions.create.mutateAsync({ name: text("name"), variety: text("variety"), supplier: text("supplier") });
      navigate(String(created.id));
    } catch (err) {
      setError((err as Error).message);
    }
  }

  const list = packets.data ?? [];
  return (
    <main className="page wide">
      <h1>Seeds</h1>
      <p className="muted">Your seed packets. Add each one with the dates from the back, then see what can be sown this month.</p>

      {canEdit && <ScanBox allotmentId={id} />}

      {!!drafts.data?.length && (
        <section className="drafts" aria-label="To review">
          <h2>To review ({drafts.data.length})</h2>
          <ul className="packets">
            {drafts.data.map((p) => (
              <li key={p.id}>
                <Link to={String(p.id)} className="packet-card">
                  <span className="packet-main">
                    <strong>{p.name}</strong>
                    <span className="muted">{[p.variety, p.supplier].filter(Boolean).join(" · ") || "Read from a photo"}</span>
                  </span>
                  <span className="badge">Draft</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {canEdit && (
        <form className="packet-add" onSubmit={(e) => void add(e)}>
          <input name="name" placeholder="Name, e.g. Tomato" aria-label="Name" required maxLength={200} />
          <input name="variety" placeholder="Variety" aria-label="Variety" maxLength={200} />
          <input name="supplier" placeholder="Supplier" aria-label="Supplier" maxLength={200} />
          <button type="submit" disabled={actions.create.isPending}>Add packet</button>
          {error && <p role="alert" className="error">{error}</p>}
        </form>
      )}

      <div className="packet-filters">
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search seeds" aria-label="Search seeds" />
        <select value={stock} onChange={(e) => setStock(e.target.value as StockLevel | "")} aria-label="Stock">
          <option value="">Any stock</option>
          {STOCK.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <label className="check">
          <input type="checkbox" checked={sowNow} onChange={(e) => setSowNow(e.target.checked)} /> Can sow in
        </label>
        <select value={month} onChange={(e) => setMonth(Number(e.target.value))} aria-label="Month" disabled={!sowNow}>
          {MONTH_NAMES.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
        </select>
      </div>

      {packets.isLoading ? (
        <p className="muted">Loading…</p>
      ) : list.length === 0 ? (
        <p className="muted">
          {q || stock || sowNow ? "No packets match." : canEdit ? "No packets yet. Add the first one above." : "No packets yet."}
        </p>
      ) : (
        <ul className="packets">
          {list.map((p) => {
            const thumb = p.photos?.find((m) => m.thumb_url)?.thumb_url;
            const grow = daysLabel(p.maturity_days_min, p.maturity_days_max);
            return (
              <li key={p.id}>
                <Link to={String(p.id)} className="packet-card">
                  {thumb ? <img src={thumb} alt="" className="packet-thumb" /> : <span className="packet-thumb none" aria-hidden="true">🌱</span>}
                  <span className="packet-main">
                    <strong>{p.name}</strong>
                    <span className="muted">{[p.variety, p.supplier].filter(Boolean).join(" · ")}</span>
                    {grow && <span className="muted">Harvest in {grow}</span>}
                    <MonthGrid calendar={p.calendar ?? {}} hideEmpty />
                  </span>
                  <span className={`badge stock-${p.stock}`}>{STOCK.find(([v]) => v === p.stock)?.[1]}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </main>
  );
}
