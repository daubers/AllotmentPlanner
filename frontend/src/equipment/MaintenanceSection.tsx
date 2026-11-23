import { useState } from "react";
import { addDays, todayISO } from "../plan/dates";
import { dayLabel } from "../plan/window";
import { useMaintenance, useMaintenanceActions } from "./hooks";

const PRESETS = ["Sharpen", "Oil", "Clean", "Service", "Check for rust", "Replace handle"];
const UNITS = ["day", "week", "month"] as const;

const nice = (iso: string) => `${dayLabel(iso)} ${iso.slice(0, 4)}`;

/** Routine maintenance of one item: when it is next due, and jobs to repeat (or do once) that become tasks. */
export default function MaintenanceSection({ allotmentId, equipmentId, name, canEdit }: { allotmentId: number; equipmentId: number; name: string; canEdit: boolean }) {
  const maintenance = useMaintenance(allotmentId, equipmentId);
  const actions = useMaintenanceActions(allotmentId, equipmentId);
  const [once, setOnce] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmStop, setConfirmStop] = useState<number | null>(null);
  const m = maintenance.data;

  async function add(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const text = (k: string) => String(f.get(k) ?? "").trim();
    const starts_on = text("starts_on");
    try {
      await actions.schedule.mutateAsync({
        title: text("title") ? `${text("title")} ${name}`.slice(0, 200) : "",
        starts_on,
        until_on: once ? starts_on : text("until_on"),
        every_n: once ? 1 : Number(text("every_n")) || 1,
        unit: once ? "month" : (text("unit") as (typeof UNITS)[number]),
      });
      setError(null);
      e.currentTarget.reset();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function stop(id: number) {
    try {
      await actions.stop.mutateAsync(id);
      setConfirmStop(null);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <section className="maintenance" aria-label="Maintenance">
      <h2>Maintenance</h2>
      <p className="muted">
        {m?.last_serviced_on ? `Last serviced ${nice(m.last_serviced_on)}.` : "No service recorded yet."}{" "}
        {m?.next_due ? (
          <>
            Next due {nice(m.next_due)}.{" "}
            {m.overdue && <span className="badge out-of-action">Overdue</span>}
          </>
        ) : (
          "Nothing scheduled."
        )}
      </p>

      {(m?.schedules ?? []).length > 0 && (
        <ul className="maintenance-list">
          {m!.schedules!.map((s) => (
            <li key={s.id}>
              <span>
                <strong>{s.title}</strong> <span className="muted">{s.rule}, until {nice(s.until_on!)}. {s.open_tasks} to do, {s.done_tasks} done.</span>
              </span>
              {canEdit &&
                (confirmStop === s.id ? (
                  <span>
                    <button type="button" className="danger" onClick={() => void stop(s.id!)}>Yes, stop it</button>{" "}
                    <button type="button" className="secondary" onClick={() => setConfirmStop(null)}>No</button>
                  </span>
                ) : (
                  <button type="button" className="secondary" onClick={() => setConfirmStop(s.id!)}>Stop</button>
                ))}
            </li>
          ))}
        </ul>
      )}

      {canEdit && (
        <form className="maintenance-form" onSubmit={(e) => void add(e)}>
          <label>
            Job
            <input name="title" list="maintenance-presets" placeholder="Sharpen, oil, service…" maxLength={150} />
            <datalist id="maintenance-presets">
              {PRESETS.map((p) => <option key={p} value={p} />)}
            </datalist>
          </label>
          <label className="check">
            <input type="checkbox" checked={once} onChange={(e) => setOnce(e.target.checked)} /> Just once
          </label>
          {!once && (
            <div className="pair">
              <label>
                Every
                <input name="every_n" type="number" min={1} max={365} defaultValue={3} />
              </label>
              <label>
                Unit
                <select name="unit" defaultValue="month">
                  {UNITS.map((u) => <option key={u} value={u}>{u}s</option>)}
                </select>
              </label>
            </div>
          )}
          <div className="pair">
            <label>
              {once ? "On" : "Starting"}
              <input name="starts_on" type="date" defaultValue={todayISO()} required />
            </label>
            {!once && (
              <label>
                Until
                <input name="until_on" type="date" defaultValue={addDays(todayISO(), 365)} required />
              </label>
            )}
          </div>
          <p className="hint">A task is made for each date, about this item. They appear on the Tasks and Today pages and on visits.</p>
          {error && <p role="alert" className="error">{error}</p>}
          <button type="submit" disabled={actions.schedule.isPending}>Schedule maintenance</button>
        </form>
      )}
    </section>
  );
}
