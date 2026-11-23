import { useState } from "react";
import Modal from "../components/Modal";
import { useSeriesActions } from "../tasks/hooks";
import { todayISO } from "./dates";
import type { PlanBed } from "./hooks";

const UNITS = ["day", "week", "month"] as const;

/** A job that repeats on a schedule on one bed (watering, weeding, feeding), made as dated tasks ahead of time. */
export default function MaintenanceDialog({
  allotmentId,
  beds,
  bedId,
  until,
  onClose,
}: {
  allotmentId: number;
  beds: PlanBed[];
  bedId: number | null;
  /** Where the schedule ends unless changed: the end of the window being looked at. */
  until: string;
  onClose(): void;
}) {
  const actions = useSeriesActions(allotmentId);
  const [bed, setBed] = useState<number>(bedId ?? beds[0]?.feature_id ?? 0);
  const [title, setTitle] = useState(`Weed ${beds.find((b) => b.feature_id === (bedId ?? beds[0]?.feature_id))?.name ?? "the bed"}`);
  const [every, setEvery] = useState("1");
  const [unit, setUnit] = useState<(typeof UNITS)[number]>("week");
  const [starts, setStarts] = useState(todayISO());
  const [ends, setEnds] = useState(until);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    try {
      await actions.create.mutateAsync({
        title: title.trim(),
        feature_id: bed || null,
        every_n: Number(every) || 1,
        unit,
        starts_on: starts,
        until_on: ends,
      });
      onClose();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <Modal title="Add a repeating job" onClose={onClose}>
      <form className="task-dialog" onSubmit={submit}>
        <label>
          Job
          <input value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={200} autoFocus />
        </label>
        <label>
          Bed
          <select
            value={bed}
            onChange={(e) => {
              const id = Number(e.target.value);
              const before = beds.find((b) => b.feature_id === bed)?.name;
              setBed(id);
              // keep a name that still says the default job, pointed at the new bed
              if (before && title === `Weed ${before}`) setTitle(`Weed ${beds.find((b) => b.feature_id === id)?.name ?? ""}`);
            }}
          >
            {beds.map((b) => (
              <option key={b.feature_id} value={b.feature_id}>
                {b.name}
              </option>
            ))}
          </select>
        </label>
        <div className="pair">
          <label>
            Every
            <input type="number" min={1} max={365} value={every} onChange={(e) => setEvery(e.target.value)} />
          </label>
          <label>
            Unit
            <select value={unit} onChange={(e) => setUnit(e.target.value as (typeof UNITS)[number])}>
              {UNITS.map((u) => (
                <option key={u} value={u}>
                  {u}s
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="pair">
          <label>
            Starting
            <input type="date" value={starts} onChange={(e) => setStarts(e.target.value)} required />
          </label>
          <label>
            Until
            <input type="date" value={ends} onChange={(e) => setEnds(e.target.value)} required />
          </label>
        </div>
        <p className="hint">A task is made for each date. Change or stop the schedule later from any of its tasks.</p>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <div className="actions">
          <button type="submit" disabled={actions.create.isPending || !bed}>
            Add job
          </button>
          <button type="button" className="secondary" onClick={onClose}>
            Cancel
          </button>
        </div>
      </form>
    </Modal>
  );
}
