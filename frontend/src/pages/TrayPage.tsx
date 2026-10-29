import { useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { uploadMedia, useMediaActions } from "../media/hooks";
import { usePackets } from "../seeds/hooks";
import {
  cellMap, colourIndex, describeCell, key, posOf, selectAll, summarise, toggle, toggleCol, toggleRow,
} from "../trays/grid";
import { useTray, useTrayActions, type CellChange } from "../trays/hooks";
import { useAllotment } from "./AllotmentLayout";

export default function TrayPage() {
  const { id, canEdit } = useAllotment();
  const trayId = Number(useParams().trayId);
  const navigate = useNavigate();
  const tray = useTray(id, trayId);
  const packets = usePackets(id);
  const actions = useTrayActions(id);
  const mediaActions = useMediaActions(id);
  const fileInput = useRef<HTMLInputElement>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [packetId, setPacketId] = useState("");
  const [count, setCount] = useState("1");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const t = tray.data;
  if (tray.isLoading) return <main className="page"><p className="muted">Loading…</p></main>;
  if (!t) return <main className="page"><p>Tray not found. <Link to="..">Back to trays</Link></p></main>;

  const cells = cellMap(t.cells);
  const names = new Map((packets.data ?? []).map((p) => [p.id, p.variety ? `${p.name} (${p.variety})` : p.name]));
  const nameOf = (pid?: number | null) => (pid == null ? undefined : names.get(pid) ?? t.kinds?.find((k) => k.packet_id === pid)?.name);
  const rows = t.rows!, cols = t.cols!;

  async function apply(set: CellChange, done: string) {
    const picked = [...selected].map(posOf);
    if (picked.length === 0) return;
    try {
      await actions.setCells.mutateAsync({ id: trayId, cells: picked, set });
      setSelected(new Set());
      setError(null);
      setNotice(done);
    } catch (err) {
      setNotice(null);
      setError((err as Error).message);
    }
  }

  async function saveDetails(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const text = (k: string) => String(f.get(k) ?? "").trim();
    try {
      await actions.patch.mutateAsync({
        id: trayId,
        name: text("name"),
        rows: Number(f.get("rows")),
        cols: Number(f.get("cols")),
        tray_type: text("tray_type"),
        location: text("location"),
        sown_on: text("sown_on") || null,
        notes: text("notes"),
        status: text("status") as "active",
      });
      setError(null);
      setNotice("Saved");
    } catch (err) {
      setNotice(null);
      setError((err as Error).message);
    }
  }

  async function addPhotos(files: FileList | null) {
    if (!files?.length) return;
    setUploading(true);
    try {
      for (const file of Array.from(files)) await uploadMedia(id, { file, trayId });
      setError(null);
      actions.refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function removeTray() {
    try {
      await actions.remove.mutateAsync(trayId);
      navigate("..", { relative: "path" });
    } catch (err) {
      setError((err as Error).message);
    }
  }

  const n = selected.size;
  return (
    <main className="page wide">
      <p><Link to="..">← All trays</Link></p>
      <h1>{t.name}</h1>
      <p className="muted">
        {rows} × {cols}{t.tray_type ? ` · ${t.tray_type}` : ""}{t.location ? ` · ${t.location}` : ""} · {summarise(t.counts) || "nothing sown yet"}
      </p>

      <div className="tray-grid-wrap">
        <table className="tray-grid" aria-label="Tray cells">
          <thead>
            <tr>
              <th scope="col" />
              {Array.from({ length: cols }, (_, c) => (
                <th key={c} scope="col">
                  <button type="button" className="link" disabled={!canEdit} onClick={() => setSelected(toggleCol(selected, c, rows))} aria-label={`Select column ${c + 1}`}>{c + 1}</button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: rows }, (_, r) => (
              <tr key={r}>
                <th scope="row">
                  <button type="button" className="link" disabled={!canEdit} onClick={() => setSelected(toggleRow(selected, r, cols))} aria-label={`Select row ${r + 1}`}>{r + 1}</button>
                </th>
                {Array.from({ length: cols }, (_, c) => {
                  const cell = cells.get(key(r, c));
                  const colour = colourIndex(cell?.packet_id, t.kinds);
                  const on = selected.has(key(r, c));
                  return (
                    <td key={c}>
                      <button
                        type="button"
                        className={`tray-cell st-${cell?.status ?? "empty"} ${colour >= 0 ? `kind-${colour}` : cell ? "kind-none" : ""}`}
                        aria-pressed={on}
                        aria-label={describeCell(r, c, cell, nameOf(cell?.packet_id))}
                        title={describeCell(r, c, cell, nameOf(cell?.packet_id))}
                        disabled={!canEdit}
                        onClick={() => setSelected(toggle(selected, key(r, c)))}
                      >
                        {cell?.status === "germinated" ? "✓" : cell?.status === "failed" ? "✕" : cell ? (cell.count ?? "") : ""}
                      </button>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
        <p className="hint">✓ came up · ✕ failed · a number is seeds sown · tap a row or column number to pick it all.</p>
      </div>

      {canEdit && (
        <section className="tray-actions" aria-label="Change the selected cells">
          <p><strong>{n}</strong> cell{n === 1 ? "" : "s"} selected{" "}
            <button type="button" className="link" onClick={() => setSelected(selectAll(rows, cols))}>Select all</button>{" "}
            <button type="button" className="link" disabled={n === 0} onClick={() => setSelected(new Set())}>Clear selection</button>
          </p>
          <div className="tray-sow">
            <label>
              Seed
              <select value={packetId} onChange={(e) => setPacketId(e.target.value)}>
                <option value="">Choose a packet…</option>
                {(packets.data ?? []).map((p) => <option key={p.id} value={p.id}>{names.get(p.id)}</option>)}
              </select>
            </label>
            <label>
              Seeds per cell
              <input type="number" min={1} max={1000} value={count} onChange={(e) => setCount(e.target.value)} />
            </label>
            <button type="button" disabled={n === 0 || !packetId || actions.setCells.isPending}
              onClick={() => void apply({ packet_id: Number(packetId), count: Number(count) || 1 }, `Sown in ${n} cell${n === 1 ? "" : "s"}`)}>
              Sow
            </button>
          </div>
          <label>
            Note for these cells
            <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} placeholder="optional" />
          </label>
          <div className="inline">
            <button type="button" className="secondary" disabled={n === 0 || actions.setCells.isPending}
              onClick={() => void apply({ status: "germinated", ...(note ? { note } : {}) }, "Marked as come up")}>Came up ✓</button>
            <button type="button" className="secondary" disabled={n === 0 || actions.setCells.isPending}
              onClick={() => void apply({ status: "failed", ...(note ? { note } : {}) }, "Marked as failed")}>Failed ✕</button>
            <button type="button" className="secondary" disabled={n === 0 || actions.setCells.isPending}
              onClick={() => void apply({ status: "sown" }, "Back to sown")}>Back to sown</button>
            <button type="button" className="secondary" disabled={n === 0 || actions.setCells.isPending}
              onClick={() => void apply({ status: "empty" }, "Cleared")}>Clear cells</button>
          </div>
        </section>
      )}
      {error && <p role="alert" className="error">{error}</p>}
      {notice && <p role="status" className="ok">{notice}</p>}

      <section>
        <h2>What's in it</h2>
        {t.kinds?.length ? (
          <ul className="tray-kinds">
            {t.kinds.map((k, i) => (
              <li key={k.packet_id}>
                <span className={`swatch kind-${i % 8}`} aria-hidden="true" />{" "}
                <Link to={`../../seeds/${k.packet_id}`} relative="path">{k.name || "Unknown seed"}{k.variety ? ` (${k.variety})` : ""}</Link>
                <span className="muted"> · {k.cells} cell{k.cells === 1 ? "" : "s"}, {k.seeds} seed{k.seeds === 1 ? "" : "s"}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">Nothing sown yet.</p>
        )}
      </section>

      <section>
        <h2>Photos</h2>
        {t.photos?.length ? (
          <ul className="packet-photos">
            {t.photos.map((m) => (
              <li key={m.id}>
                <a href={m.url} target="_blank" rel="noreferrer noopener">
                  {m.thumb_url ? <img src={m.thumb_url} alt={m.caption || m.filename} /> : <span className="muted">{m.status === "failed" ? "Couldn't read this photo" : "Processing…"}</span>}
                </a>
                <span className="muted">{(m.taken_at ?? "").slice(0, 10)}</span>
                {canEdit && (
                  <button type="button" className="secondary" onClick={() => mediaActions.remove.mutate(m.id!, { onSuccess: actions.refresh })}>Remove</button>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No photos yet. A photo every few days shows how the tray is getting on.</p>
        )}
        {canEdit && (
          <label className="file">
            <span className="secondary button">{uploading ? "Uploading…" : "Add photos"}</span>
            <input ref={fileInput} type="file" accept="image/*" multiple className="sr-only" disabled={uploading} onChange={(e) => void addPhotos(e.target.files)} />
          </label>
        )}
      </section>

      <details className="tray-details">
        <summary>Tray details</summary>
        <form className="packet-form" onSubmit={(e) => void saveDetails(e)} key={`${t.id}-${t.updated_at}`}>
          <fieldset disabled={!canEdit}>
            <legend>About</legend>
            <label>Name<input name="name" defaultValue={t.name} required maxLength={200} /></label>
            <label>Type<input name="tray_type" defaultValue={t.tray_type} maxLength={100} /></label>
            <label>Where<input name="location" defaultValue={t.location} maxLength={200} placeholder="e.g. greenhouse, left shelf" /></label>
            <label>Sown on<input name="sown_on" type="date" defaultValue={t.sown_on ?? ""} /></label>
            <label>Rows<input name="rows" type="number" min={1} max={30} defaultValue={rows} required /></label>
            <label>Columns<input name="cols" type="number" min={1} max={30} defaultValue={cols} required /></label>
            <label>
              State
              <select name="status" defaultValue={t.status}>
                <option value="active">Growing on</option>
                <option value="planted_out">Planted out</option>
                <option value="finished">Finished</option>
              </select>
            </label>
          </fieldset>
          <label>Notes<textarea name="notes" rows={3} defaultValue={t.notes} disabled={!canEdit} maxLength={5000} /></label>
          {canEdit && <button type="submit" disabled={actions.patch.isPending}>Save</button>}
        </form>
        {canEdit && (
          <p className="danger-zone">
            {confirmDelete ? (
              <button type="button" className="danger" onClick={() => void removeTray()}>Really delete this tray?</button>
            ) : (
              <button type="button" className="secondary" onClick={() => setConfirmDelete(true)}>Delete tray</button>
            )}
            <span className="hint"> Its photos stay in the photo timeline.</span>
          </p>
        )}
      </details>
    </main>
  );
}
