import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import Modal from "../components/Modal";
import { usePackets } from "../seeds/hooks";
import { areaFromPercent, hint, percentOfBed, suggestArea, suggestCount } from "./area";
import { basisFromCrop, basisFromPacket, defaultDates, type Basis, type Method } from "./basis";
import { addDays, todayISO } from "./dates";
import { useCrops, usePlanActions, type PlanItem, type PlanItemInput } from "./hooks";
import { dayLabel } from "./window";

type Bed = { id: number; name: string; area: number | null };
type Unit = "m2" | "pct";

const sourceOf = (item?: PlanItem): string =>
  item?.packet_id ? `packet:${item.packet_id}` : item?.crop_key ? `crop:${item.crop_key}` : "";

/** Add a crop to a bed's plan, or edit one. A new one can be repeated as a succession. */
export default function PlanItemDialog({
  allotmentId,
  bed,
  item,
  onClose,
}: {
  allotmentId: number;
  bed: Bed;
  item?: PlanItem;
  onClose(): void;
}) {
  const crops = useCrops();
  const packets = usePackets(allotmentId);
  const actions = usePlanActions(allotmentId);
  const editing = !!item;

  const [source, setSource] = useState(sourceOf(item));
  const [name, setName] = useState(item?.name ?? "");
  const [method, setMethod] = useState<Method>(item?.method ?? "direct_sow");
  const [count, setCount] = useState(item?.plant_count ? String(item.plant_count) : "");
  const [area, setArea] = useState(item?.area_m2 ? String(item.area_m2) : "");
  const [unit, setUnit] = useState<Unit>("m2");
  const [sowOn, setSowOn] = useState(item?.sow_on ?? todayISO());
  const [plantOutOn, setPlantOutOn] = useState(item?.plant_out_on ?? "");
  const [endOn, setEndOn] = useState(item?.end_on ?? addDays(todayISO(), 90));
  const [notes, setNotes] = useState(item?.notes ?? "");
  const [status, setStatus] = useState<"planned" | "done" | "skipped">(item?.status ?? "planned");
  const [repeat, setRepeat] = useState(false);
  const [every, setEvery] = useState("14");
  const [times, setTimes] = useState("4");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const basis: Basis | null = useMemo(() => {
    if (source.startsWith("packet:")) {
      const p = packets.data?.find((x) => x.id === Number(source.slice(7)));
      return p ? basisFromPacket(p) : null;
    }
    if (source.startsWith("crop:")) {
      const c = crops.data?.find((x) => x.key === source.slice(5));
      return c ? basisFromCrop(c) : null;
    }
    return null;
  }, [source, packets.data, crops.data]);

  const bedArea = bed.area;
  const areaM2 = unit === "pct" && bedArea ? areaFromPercent(Number(area), bedArea) : Number(area);
  const spacing = basis?.spacing ?? { plant: null, row: null };
  const countN = Number(count) || null;
  const note = hint(countN, spacing);
  const fits = areaM2 > 0 ? suggestCount(areaM2, spacing) : null;
  const suggested = countN ? suggestArea(countN, spacing) : null;

  function choose(value: string) {
    setSource(value);
    const b = value.startsWith("packet:")
      ? (() => {
          const p = packets.data?.find((x) => x.id === Number(value.slice(7)));
          return p ? basisFromPacket(p) : null;
        })()
      : value.startsWith("crop:")
        ? (() => {
            const c = crops.data?.find((x) => x.key === value.slice(5));
            return c ? basisFromCrop(c) : null;
          })()
        : null;
    if (!b) return;
    setName(b.name);
    setMethod(b.method);
    const d = defaultDates(b, todayISO());
    setSowOn(d.sow_on);
    setPlantOutOn(d.plant_out_on ?? "");
    setEndOn(d.end_on);
    if (b.successionDays) setEvery(String(b.successionDays));
  }

  function useSuggestion() {
    if (suggested === null) return;
    setArea(String(unit === "pct" && bedArea ? percentOfBed(suggested, bedArea) : suggested));
  }

  function switchUnit(next: Unit) {
    if (next === unit) return;
    const current = Number(area);
    if (bedArea && current > 0) {
      setArea(String(next === "pct" ? percentOfBed(current, bedArea) : areaFromPercent(current, bedArea)));
    }
    setUnit(next);
  }

  const body = (): PlanItemInput => ({
    feature_id: bed.id,
    crop_key: basis?.cropKey ?? item?.crop_key ?? null,
    packet_id: basis?.packetId ?? null,
    name: name.trim(),
    method,
    area_m2: areaM2,
    plant_count: countN,
    sow_on: sowOn,
    plant_out_on: method === "transplant" ? plantOutOn || null : null,
    end_on: endOn,
    notes: notes.trim(),
  });

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    if (!(areaM2 > 0)) return setError("Say how much space it needs.");
    if (!name.trim() && !basis) return setError("Choose a crop or give it a name.");
    try {
      if (item) {
        await actions.update.mutateAsync({ id: item.id!, body: { ...body(), status } });
      } else if (repeat) {
        await actions.succession.mutateAsync({ item: body(), interval_days: Number(every), count: Number(times) });
      } else {
        await actions.create.mutateAsync(body());
      }
      onClose();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function remove() {
    try {
      await actions.remove.mutateAsync(item!.id!);
      onClose();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  const pending = actions.create.isPending || actions.update.isPending || actions.succession.isPending;
  const preview = repeat && Number(every) > 0 && Number(times) > 1
    ? Array.from({ length: Math.min(Number(times), 30) }, (_, i) => dayLabel(addDays(sowOn, i * Number(every))))
    : [];

  return (
    <Modal title={editing ? `Edit ${item!.name}` : `Add a crop to ${bed.name}`} onClose={onClose}>
      <form className="task-dialog plan-form" onSubmit={submit}>
        <label>
          Crop
          <select value={source} onChange={(e) => choose(e.target.value)}>
            <option value="">Choose a crop or packet…</option>
            {!!packets.data?.length && (
              <optgroup label="My seed packets">
                {packets.data.map((p) => (
                  <option key={p.id} value={`packet:${p.id}`}>
                    {p.variety ? `${p.name} (${p.variety})` : p.name}
                  </option>
                ))}
              </optgroup>
            )}
            <optgroup label="Crops">
              {(crops.data ?? []).map((c) => (
                <option key={c.key} value={`crop:${c.key}`}>
                  {c.name}
                </option>
              ))}
            </optgroup>
          </select>
        </label>
        <label>
          Name on the plan
          <input value={name} onChange={(e) => setName(e.target.value)} maxLength={120} />
        </label>
        <div className="pair">
          <label>
            How
            <select value={method} onChange={(e) => setMethod(e.target.value as Method)}>
              <option value="direct_sow">Sow in the bed</option>
              <option value="transplant">Sow in a tray, plant out</option>
            </select>
          </label>
          <label>
            Plants (optional)
            <input type="number" min={1} value={count} onChange={(e) => setCount(e.target.value)} />
          </label>
        </div>
        <div className="pair">
          <label>
            Space
            <input type="number" min={0.1} step="any" value={area} onChange={(e) => setArea(e.target.value)} required />
          </label>
          <label>
            Measured in
            <select value={unit} onChange={(e) => switchUnit(e.target.value as Unit)} aria-label="Unit">
              <option value="m2">m²</option>
              <option value="pct" disabled={!bedArea}>
                % of the bed
              </option>
            </select>
          </label>
        </div>
        {(note || fits !== null) && (
          <p className="hint plan-hint">
            {note}
            {fits !== null && !countN ? ` Room for about ${fits} plants.` : ""}
            {suggested !== null && (
              <>
                {" "}
                <button type="button" className="link" onClick={useSuggestion}>
                  Use {suggested} m²
                </button>
              </>
            )}
            {" (approximate)"}
          </p>
        )}
        {bedArea ? <p className="hint">{bed.name} is about {Math.round(bedArea * 10) / 10} m².</p> : null}
        <div className="pair">
          <label>
            Sow on
            <input type="date" value={sowOn} onChange={(e) => setSowOn(e.target.value)} required />
          </label>
          {method === "transplant" && (
            <label>
              Plant out on
              <input type="date" value={plantOutOn} onChange={(e) => setPlantOutOn(e.target.value)} required />
            </label>
          )}
          <label>
            Bed free again on
            <input type="date" value={endOn} onChange={(e) => setEndOn(e.target.value)} required />
          </label>
        </div>
        <label>
          Notes
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} maxLength={5000} />
        </label>
        {editing && (
          <label>
            Status
            <select value={status} onChange={(e) => setStatus(e.target.value as typeof status)}>
              <option value="planned">Planned</option>
              <option value="done">Done</option>
              <option value="skipped">Skipped</option>
            </select>
          </label>
        )}
        {!editing && (
          <fieldset className="plan-repeat">
            <label className="check">
              <input type="checkbox" checked={repeat} onChange={(e) => setRepeat(e.target.checked)} />
              Repeat as a succession
            </label>
            {repeat && (
              <>
                <div className="pair">
                  <label>
                    Every (days)
                    <input type="number" min={1} max={365} value={every} onChange={(e) => setEvery(e.target.value)} />
                  </label>
                  <label>
                    Sowings in all
                    <input type="number" min={1} max={30} value={times} onChange={(e) => setTimes(e.target.value)} />
                  </label>
                </div>
                {preview.length > 0 && <p className="hint">Sowings: {preview.join(", ")}</p>}
              </>
            )}
          </fieldset>
        )}
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        {item && item.status === "planned" && (
          <p className="hint plan-plant">
            {item.method === "direct_sow" ? (
              <>
                Sown now?{" "}
                <Link to={`/allotments/${allotmentId}/beds/${bed.id}?planItem=${item.id}`}>Plant this in {bed.name}</Link> to draw its area and
                record the planting.
              </>
            ) : (
              <>
                This one is sown in a tray first. Sow it on the Trays page, then plant it out into {bed.name}; mark it done here
                when it is in.
              </>
            )}
          </p>
        )}
        {item?.planting_id ? (
          <p className="hint plan-plant">
            Planted. <Link to={`/allotments/${allotmentId}/beds/${bed.id}`}>See it in {bed.name}</Link>
          </p>
        ) : null}
        <div className="actions">
          <button type="submit" disabled={pending}>
            {editing ? "Save" : repeat ? "Add succession" : "Add to plan"}
          </button>
          {editing &&
            (confirmDelete ? (
              <button type="button" className="danger" onClick={() => void remove()}>
                Really remove it?
              </button>
            ) : (
              <button type="button" className="secondary" onClick={() => setConfirmDelete(true)}>
                Remove
              </button>
            ))}
        </div>
      </form>
    </Modal>
  );
}
