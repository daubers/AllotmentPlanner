import { useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { uploadMedia, useMediaActions } from "../media/hooks";
import MonthGrid from "../seeds/MonthGrid";
import { ACTIVITIES, STOCK, SUN, toggleMonth, type Calendar } from "../seeds/calendar";
import { usePacket, usePacketActions, type PacketPatch } from "../seeds/hooks";
import { summarise } from "../trays/grid";
import { useTrays } from "../trays/hooks";
import { useAllotment } from "./AllotmentLayout";

const num = (v: FormDataEntryValue | null): number | null => (v === null || String(v).trim() === "" ? null : Number(v));

export default function PacketPage() {
  const { id, canEdit } = useAllotment();
  const packetId = Number(useParams().packetId);
  const navigate = useNavigate();
  const packet = usePacket(id, packetId);
  const actions = usePacketActions(id);
  const mediaActions = useMediaActions(id);
  const trays = useTrays(id, { packetId });
  const fileInput = useRef<HTMLInputElement>(null);
  const [draft, setDraft] = useState<{ key: string; calendar: Calendar } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const p = packet.data;
  if (packet.isLoading) return <main className="page"><p className="muted">Loading…</p></main>;
  if (!p) return <main className="page"><p>Packet not found. <Link to="..">Back to seeds</Link></p></main>;

  // The calendar being edited, reset whenever the saved packet changes.
  const stamp = `${p.id}-${p.updated_at}`;
  const calendar: Calendar = draft?.key === stamp ? draft.calendar : (p.calendar ?? {});

  function toggle(activity: keyof Calendar, month: number) {
    setDraft({ key: stamp, calendar: { ...calendar, [activity]: toggleMonth(calendar[activity], month) } });
  }

  async function save(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const text = (k: string) => String(f.get(k) ?? "").trim();
    const body: PacketPatch & { id: number } = {
      id: packetId,
      name: text("name"),
      variety: text("variety"),
      supplier: text("supplier"),
      latin_name: text("latin_name"),
      notes: text("notes"),
      stock: text("stock") as "full",
      sun: (text("sun") || null) as "full" | null,
      sow_depth_mm: num(f.get("sow_depth_mm")),
      spacing_plant_cm: num(f.get("spacing_plant_cm")),
      spacing_row_cm: num(f.get("spacing_row_cm")),
      germinate_days_min: num(f.get("germinate_days_min")),
      germinate_days_max: num(f.get("germinate_days_max")),
      maturity_days_min: num(f.get("maturity_days_min")),
      maturity_days_max: num(f.get("maturity_days_max")),
      best_before_year: num(f.get("best_before_year")),
      calendar,
    };
    try {
      await actions.patch.mutateAsync(body);
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
      for (const file of Array.from(files)) await uploadMedia(id, { file, packetId });
      setError(null);
      actions.refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function removePacket() {
    try {
      await actions.remove.mutateAsync(packetId);
      navigate("..", { relative: "path" });
    } catch (err) {
      setError((err as Error).message);
    }
  }

  const field = (name: string, label: string, value: number | null | undefined, unit?: string) => (
    <label>
      {label}
      <input name={name} type="number" min={0} inputMode="numeric" defaultValue={value ?? ""} disabled={!canEdit} placeholder={unit} />
    </label>
  );

  return (
    <main className="page wide">
      <p><Link to="..">← All seeds</Link></p>
      <h1>{p.name}{p.variety ? <span className="muted"> · {p.variety}</span> : null}</h1>

      <form className="packet-form" onSubmit={(e) => void save(e)} key={stamp}>
        <fieldset disabled={!canEdit}>
          <legend>About</legend>
          <label>Name<input name="name" defaultValue={p.name} required maxLength={200} /></label>
          <label>Variety<input name="variety" defaultValue={p.variety} maxLength={200} /></label>
          <label>Supplier<input name="supplier" defaultValue={p.supplier} maxLength={200} /></label>
          <label>Latin name<input name="latin_name" defaultValue={p.latin_name} maxLength={200} /></label>
          <label>
            Stock
            <select name="stock" defaultValue={p.stock}>{STOCK.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
          </label>
          <label>Best before (year){" "}
            <input name="best_before_year" type="number" min={2000} max={2100} defaultValue={p.best_before_year ?? ""} placeholder="e.g. 2027" />
          </label>
        </fieldset>

        <fieldset disabled={!canEdit}>
          <legend>Growing</legend>
          <label>
            Sun
            <select name="sun" defaultValue={p.sun ?? ""}>
              <option value="">Not stated</option>
              {SUN.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </label>
          {field("sow_depth_mm", "Sowing depth (mm)", p.sow_depth_mm)}
          {field("spacing_plant_cm", "Space between plants (cm)", p.spacing_plant_cm)}
          {field("spacing_row_cm", "Space between rows (cm)", p.spacing_row_cm)}
          {field("germinate_days_min", "Germinates in, from (days)", p.germinate_days_min)}
          {field("germinate_days_max", "Germinates in, to (days)", p.germinate_days_max)}
          {field("maturity_days_min", "Ready in, from (days)", p.maturity_days_min)}
          {field("maturity_days_max", "Ready in, to (days)", p.maturity_days_max)}
        </fieldset>

        <fieldset disabled={!canEdit}>
          <legend>When</legend>
          <p className="hint">{canEdit ? "Tap a month to switch it on or off for each job." : "The months from the packet."} Today's month is outlined.</p>
          <MonthGrid calendar={calendar} onToggle={canEdit ? toggle : undefined} />
          <ul className="muted legend">
            {ACTIVITIES.map((a) => <li key={a.key} className={`act-${a.key}`}><span className="key" /> {a.label}</li>)}
          </ul>
        </fieldset>

        <label>Notes<textarea name="notes" rows={3} defaultValue={p.notes} disabled={!canEdit} maxLength={5000} /></label>

        {error && <p role="alert" className="error">{error}</p>}
        {notice && <p role="status" className="ok">{notice}</p>}
        {canEdit && <button type="submit" disabled={actions.patch.isPending}>Save</button>}
      </form>

      <section>
        <h2>In trays</h2>
        {trays.data?.length ? (
          <ul>
            {trays.data.map((t) => (
              <li key={t.id}>
                <Link to={`../../trays/${t.id}`} relative="path">{t.name}</Link>
                <span className="muted"> · {summarise(t.counts)}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">Not sown in any tray yet.</p>
        )}
      </section>

      <section>
        <h2>Photos</h2>
        <p className="muted">The front and back of the packet.</p>
        {p.photos?.length ? (
          <ul className="packet-photos">
            {p.photos.map((m) => (
              <li key={m.id}>
                <a href={m.url} target="_blank" rel="noreferrer noopener">
                  {m.thumb_url ? <img src={m.thumb_url} alt={m.caption || m.filename} /> : <span className="muted">{m.status === "failed" ? "Couldn't read this photo" : "Processing…"}</span>}
                </a>
                {canEdit && (
                  <button type="button" className="secondary" onClick={() => mediaActions.remove.mutate(m.id!, { onSuccess: actions.refresh })}>
                    Remove
                  </button>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No photos yet.</p>
        )}
        {canEdit && (
          <label className="file">
            <span className="secondary button">{uploading ? "Uploading…" : "Add photos"}</span>
            <input ref={fileInput} type="file" accept="image/*" multiple className="sr-only" disabled={uploading} onChange={(e) => void addPhotos(e.target.files)} />
          </label>
        )}
      </section>

      {canEdit && (
        <section className="danger-zone">
          {confirmDelete ? (
            <button type="button" className="danger" onClick={() => void removePacket()}>Really delete this packet?</button>
          ) : (
            <button type="button" className="secondary" onClick={() => setConfirmDelete(true)}>Delete packet</button>
          )}
          <span className="hint"> Its photos stay in the photo timeline.</span>
        </section>
      )}
    </main>
  );
}
