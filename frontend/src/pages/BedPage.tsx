import { useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { uploadMedia, useMedia, useMediaActions } from "../media/hooks";
import { areaLabel, colourOf, polygonOf, ringOf, type LonLat } from "../plantings/geometry";
import { STATUSES, STATUS_LABEL, useBeds, usePlantingActions, usePlantings, type Planting } from "../plantings/hooks";
import RegionEditor, { type Shown } from "../plantings/RegionEditor";
import InUse from "../equipment/InUse";
import { useBookings } from "../equipment/hooks";
import { usePlanItem } from "../plan/hooks";
import { usePackets } from "../seeds/hooks";
import SuggestTasks from "../tasks/SuggestTasks";
import { useAllotment } from "./AllotmentLayout";

const today = () => new Date().toISOString().slice(0, 10);
const nameOf = (p: Planting) => (p.packet_name ? (p.packet_variety ? `${p.packet_name} (${p.packet_variety})` : p.packet_name) : "Unknown seed");

export default function BedPage() {
  const { id, canEdit } = useAllotment();
  const featureId = Number(useParams().featureId);
  const [params, setParams] = useSearchParams();
  const planItem = usePlanItem(id, Number(params.get("planItem")) || null).data;
  // Only a crop still waiting to be planted, in this bed, is carried out by the planting being added.
  const fromPlan = planItem && planItem.status === "planned" && planItem.feature_id === featureId ? planItem : null;
  const beds = useBeds(id);
  const plantings = usePlantings(id, { featureId });
  const packets = usePackets(id, { status: "active" });
  const actions = usePlantingActions(id);
  const inUse = useBookings(id, { featureId });
  const [points, setPoints] = useState<LonLat[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [showDone, setShowDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);

  const bed = beds.data?.find((b) => b.id === featureId);
  if (beds.isLoading) return <main className="page"><p className="muted">Loading…</p></main>;
  if (!bed) return <main className="page"><p>Bed not found. <Link to="..">Back to beds</Link></p></main>;

  const all = plantings.data ?? [];
  const live = all.filter((p) => ["sown", "growing", "harvesting"].includes(p.status ?? ""));
  const shown = showDone ? all : live;
  const regions: Shown[] = shown.map((p) => ({ id: p.id!, label: nameOf(p), ring: ringOf(p.region), colour: colourOf(p.packet_id), muted: !live.includes(p) }));

  async function add(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const text = (k: string) => String(f.get(k) ?? "").trim();
    try {
      const made = await actions.create.mutateAsync({
        feature_id: featureId,
        packet_id: text("packet_id") ? Number(text("packet_id")) : null,
        region: polygonOf(points),
        count: text("count") ? Number(text("count")) : null,
        sown_on: text("sown_on") || null,
        notes: text("notes"),
        plan_item_id: fromPlan?.id ?? null,
      });
      if (fromPlan) setParams({}, { replace: true }); // the plan item is done now
      setPoints([]);
      setError(null);
      setWarnings(made.warnings ?? []);
      setSelected(made.id ?? null);
      e.currentTarget.reset();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <main className="page wide">
      <p><Link to="..">← All beds</Link></p>
      <h1>{bed.name}</h1>
      <RegionEditor bed={bed.ring} others={regions} points={points} onChange={canEdit ? setPoints : undefined} selectedId={selected} title={`Sketch of ${bed.name}`} />
      <label className="check"><input type="checkbox" checked={showDone} onChange={(e) => setShowDone(e.target.checked)} /> Show finished and failed too</label>

      {canEdit && (
        <section aria-label="Add a planting">
          <h2>Add a planting</h2>
          <p className="muted">Click the corners of the area on the sketch, then say what went in.</p>
          {fromPlan && (
            <p role="status" className="plan-banner">
              Planting from your plan: <strong>{fromPlan.name}</strong>, about {fromPlan.area_m2} m²
              {fromPlan.plant_count ? ` for ${fromPlan.plant_count} plants` : ""}. Draw its area, then add the planting and the plan item is
              marked done. <Link to={`/allotments/${id}/plan`}>Back to the plan</Link>
            </p>
          )}
          <form className="planting-form" key={fromPlan?.id ?? "new"} onSubmit={(e) => void add(e)}>
            <label>
              Seed
              <select name="packet_id" defaultValue={fromPlan?.packet_id ?? ""}>
                <option value="">Not in the library</option>
                {(packets.data ?? []).map((p) => <option key={p.id} value={p.id}>{p.variety ? `${p.name} (${p.variety})` : p.name}</option>)}
              </select>
            </label>
            <label>Seeds or plants<input name="count" type="number" min={1} placeholder="optional" defaultValue={fromPlan?.plant_count ?? ""} /></label>
            <label>Sown on<input name="sown_on" type="date" defaultValue={today()} /></label>
            <label className="wide">Notes<input name="notes" maxLength={5000} placeholder="optional" defaultValue={fromPlan?.notes ?? ""} /></label>
            <button type="submit" disabled={points.length < 3 || actions.create.isPending}>Add planting</button>
          </form>
          {error && <p role="alert" className="error">{error}</p>}
          {warnings.length > 0 && <ul className="warnings" role="status">{warnings.map((w) => <li key={w}>{w}</li>)}</ul>}
        </section>
      )}

      <InUse
        allotmentId={id}
        title="Equipment in use"
        bookings={inUse.data ?? []}
        canEdit={canEdit}
        show="equipment"
        add={{ target: { kind: "feature", id: featureId, label: bed.name } }}
      />

      <section aria-label="Plantings">
        <h2>In this bed</h2>
        {shown.length === 0 ? (
          <p className="muted">Nothing {showDone ? "recorded" : "growing"} in this bed yet.</p>
        ) : (
          <ul className="plantings">
            {shown.map((p) => (
              <PlantingCard key={p.id} planting={p} open={selected === p.id} onToggle={() => setSelected(selected === p.id ? null : p.id!)} canEdit={canEdit} allotmentId={id} />
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}

function PlantingCard({ planting: p, open, onToggle, canEdit, allotmentId }: { planting: Planting; open: boolean; onToggle(): void; canEdit: boolean; allotmentId: number }) {
  const actions = usePlantingActions(allotmentId);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [confirm, setConfirm] = useState(false);

  async function save(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const text = (k: string) => String(f.get(k) ?? "").trim();
    try {
      await actions.patch.mutateAsync({
        id: p.id!,
        status: text("status") as "sown",
        planted_on: text("planted_on") || null,
        harvested_on: text("harvested_on") || null,
        count: text("count") ? Number(text("count")) : null,
        notes: text("notes"),
      });
      setError(null);
      setNotice("Saved");
    } catch (err) {
      setNotice(null);
      setError((err as Error).message);
    }
  }

  return (
    <li className={`planting${open ? " open" : ""}`}>
      <button type="button" className="planting-head" onClick={onToggle} aria-expanded={open}>
        <span className="swatch" style={{ background: colourOf(p.packet_id) }} aria-hidden="true" />
        <strong>{nameOf(p)}</strong>
        <span className="muted">{areaLabel(p.area_m2 ?? 0)}{p.count ? ` · ${p.count}` : ""}</span>
        <span className="badge">{STATUS_LABEL[p.status ?? ""] ?? p.status}</span>
      </button>
      {open && (
        <div className="planting-body">
          <p className="muted">
            {p.method === "transplant" ? "Planted out" : "Sown in the bed"}
            {p.tray_id ? <> from <Link to={`../../trays/${p.tray_id}`} relative="path">its tray</Link></> : null}
            {p.sown_on ? ` · sown ${p.sown_on}` : ""}{p.planted_on ? ` · planted ${p.planted_on}` : ""}{p.harvested_on ? ` · harvested ${p.harvested_on}` : ""}
          </p>
          <form className="packet-form" onSubmit={(e) => void save(e)} key={p.updated_at}>
            <fieldset disabled={!canEdit}>
              <legend>Details</legend>
              <label>State<select name="status" defaultValue={p.status}>{STATUSES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
              <label>Planted on<input name="planted_on" type="date" defaultValue={p.planted_on ?? ""} /></label>
              <label>Harvested on<input name="harvested_on" type="date" defaultValue={p.harvested_on ?? ""} /></label>
              <label>Seeds or plants<input name="count" type="number" min={1} defaultValue={p.count ?? ""} /></label>
              <label className="wide">Notes<input name="notes" defaultValue={p.notes} maxLength={5000} /></label>
            </fieldset>
            {error && <p role="alert" className="error">{error}</p>}
            {notice && <p role="status" className="ok">{notice}</p>}
            {canEdit && (
              <div className="inline">
                <button type="submit" disabled={actions.patch.isPending}>Save</button>
                {confirm ? (
                  <button type="button" className="danger" onClick={() => void actions.remove.mutateAsync(p.id!).catch((err: Error) => setError(err.message))}>Really delete this planting?</button>
                ) : (
                  <button type="button" className="secondary" onClick={() => setConfirm(true)}>Delete</button>
                )}
              </div>
            )}
          </form>
          {canEdit && <div className="toolbar"><SuggestTasks allotmentId={allotmentId} target={{ kind: "planting", id: p.id! }} /></div>}
          <PlantingPhotos plantingId={p.id!} allotmentId={allotmentId} canEdit={canEdit} />
        </div>
      )}
    </li>
  );
}

function PlantingPhotos({ plantingId, allotmentId, canEdit }: { plantingId: number; allotmentId: number; canEdit: boolean }) {
  const media = useMedia(allotmentId, { plantingId });
  const mediaActions = useMediaActions(allotmentId);
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function add(files: FileList | null) {
    if (!files?.length) return;
    setBusy(true);
    try {
      for (const file of Array.from(files)) await uploadMedia(allotmentId, { file, plantingId });
      setError(null);
      mediaActions.refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  }

  return (
    <div className="planting-photos">
      <h3>Photos</h3>
      {media.data?.length ? (
        <ul className="packet-photos">
          {media.data.map((m) => (
            <li key={m.id}>
              <a href={m.url} target="_blank" rel="noreferrer noopener">
                {m.thumb_url ? <img src={m.thumb_url} alt={m.caption || m.filename} /> : <span className="muted">Processing…</span>}
              </a>
              <span className="muted">{(m.taken_at ?? "").slice(0, 10)}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">No photos yet.</p>
      )}
      {canEdit && (
        <label className="file">
          <span className="secondary button">{busy ? "Uploading…" : "Add photos"}</span>
          <input ref={input} type="file" accept="image/*" multiple className="sr-only" aria-label="Photos of this planting" disabled={busy} onChange={(e) => void add(e.target.files)} />
        </label>
      )}
      {error && <p role="alert" className="error">{error}</p>}
    </div>
  );
}
