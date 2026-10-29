import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { daysSince, summarise } from "../trays/grid";
import { useTrayActions, useTrays } from "../trays/hooks";
import { useAllotment } from "./AllotmentLayout";

export default function TraysPage() {
  const { id, canEdit } = useAllotment();
  const navigate = useNavigate();
  const [showFinished, setShowFinished] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const trays = useTrays(id);
  const actions = useTrayActions(id);

  async function add(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const text = (k: string) => String(f.get(k) ?? "").trim();
    try {
      const created = await actions.create.mutateAsync({
        name: text("name"),
        rows: Number(f.get("rows")),
        cols: Number(f.get("cols")),
        tray_type: text("tray_type"),
        sown_on: text("sown_on") || null,
      });
      navigate(String(created.id));
    } catch (err) {
      setError((err as Error).message);
    }
  }

  const all = trays.data ?? [];
  const list = all.filter((t) => showFinished || t.status !== "finished");
  const hidden = all.length - list.length;
  return (
    <main className="page wide">
      <h1>Seed trays</h1>
      <p className="muted">What is sown where. Open a tray to fill its cells and mark seeds as they come up.</p>

      {canEdit && (
        <form className="tray-add" onSubmit={(e) => void add(e)}>
          <input name="name" placeholder="Name, e.g. Greenhouse tray 1" aria-label="Name" required maxLength={200} />
          <input name="rows" type="number" min={1} max={30} defaultValue={4} aria-label="Rows" title="Rows" required />
          <span aria-hidden="true">×</span>
          <input name="cols" type="number" min={1} max={30} defaultValue={6} aria-label="Columns" title="Columns" required />
          <input name="tray_type" placeholder="Type, e.g. module tray" aria-label="Type" maxLength={100} />
          <input name="sown_on" type="date" aria-label="Sown on" title="Sown on" />
          <button type="submit" disabled={actions.create.isPending}>Add tray</button>
          {error && <p role="alert" className="error">{error}</p>}
        </form>
      )}

      {trays.isLoading ? (
        <p className="muted">Loading…</p>
      ) : list.length === 0 ? (
        <p className="muted">{canEdit ? "No trays yet. Add the first one above." : "No trays yet."}</p>
      ) : (
        <ul className="packets">
          {list.map((t) => {
            const age = daysSince(t.sown_on);
            return (
              <li key={t.id}>
                <Link to={String(t.id)} className="packet-card">
                  <span className="packet-main">
                    <strong>{t.name}</strong>
                    <span className="muted">
                      {t.rows} × {t.cols}
                      {t.tray_type ? ` · ${t.tray_type}` : ""}
                      {t.location ? ` · ${t.location}` : ""}
                      {age != null && age >= 0 ? ` · sown ${age === 0 ? "today" : `${age} day${age === 1 ? "" : "s"} ago`}` : ""}
                    </span>
                    <span>{summarise(t.counts) || "Nothing sown yet"}</span>
                    {!!t.kinds?.length && <span className="muted">{t.kinds.map((k) => k.name || "Unknown seed").join(", ")}</span>}
                  </span>
                  {t.status !== "active" && <span className="badge">{t.status === "finished" ? "finished" : "planted out"}</span>}
                </Link>
              </li>
            );
          })}
        </ul>
      )}
      {hidden > 0 && (
        <button type="button" className="link" onClick={() => setShowFinished(true)}>
          Show {hidden} finished tray{hidden === 1 ? "" : "s"}
        </button>
      )}
      {showFinished && all.some((t) => t.status === "finished") && (
        <button type="button" className="link" onClick={() => setShowFinished(false)}>Hide finished trays</button>
      )}
    </main>
  );
}
