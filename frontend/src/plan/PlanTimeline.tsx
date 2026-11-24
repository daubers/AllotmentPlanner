import type { Booking } from "../equipment/hooks";
import { toDay } from "./dates";
import type { PlanBed, PlanItem } from "./hooks";
import { barStyle, currentKey, dayLabel, peakUsage, type Win } from "./window";

const widthOf = (m: { start: string; end: string }) => toDay(m.end) - toDay(m.start);

/** One bed's twelve months: how full it is each month, then a bar per crop (a lighter lead-in for tray time). */
export default function PlanTimeline({ win, bed, onEdit, bookings = [] }: { win: Win; bed: PlanBed; onEdit(item: PlanItem): void; bookings?: Booking[] }) {
  const items = bed.items ?? [];
  const area = bed.area_m2 ?? null;
  const peaks = area ? peakUsage(items, win) : [];
  const now = currentKey();
  const over = (bed.conflicts ?? []).flatMap((c) => c.item_ids ?? []);

  return (
    <div className="plan-timeline" role="group" aria-label={`Plan for ${bed.name}`}>
      <div className="plan-row plan-months">
        <span />
        <div className="plan-track">
          {win.months.map((m) => (
            <span key={m.key} className={`plan-month${m.key === now ? " now" : ""}`} style={{ flexGrow: widthOf(m) }}>
              {m.label}
              {m.month === 1 || m === win.months[0] ? <small>{m.year}</small> : null}
            </span>
          ))}
        </div>
      </div>

      {area ? (
        <div className="plan-row plan-capacity">
          <span className="plan-name muted">Space used</span>
          <div className="plan-track">
            {win.months.map((m, i) => {
              const used = peaks[i];
              const pct = Math.min(100, (used / area) * 100);
              const full = used > area + 0.01;
              return (
                <span
                  key={m.key}
                  className={`plan-cap${full ? " over" : ""}`}
                  style={{ flexGrow: widthOf(m) }}
                  title={`${used} of ${Math.round(area * 10) / 10} m² used${full ? " (overbooked)" : ""}`}
                >
                  <span style={{ height: `${pct}%` }} />
                  <small>{used > 0 ? `${Math.round((used / area) * 100)}%` : ""}</small>
                </span>
              );
            })}
          </div>
        </div>
      ) : (
        <p className="muted plan-note">This bed has no area drawn, so its space can't be checked.</p>
      )}

      {items.length === 0 && <p className="muted plan-note">Nothing planned in this window.</p>}
      {items.map((item) => {
        const startsIn = item.plant_out_on ?? item.sow_on!;
        const bar = barStyle(startsIn, item.end_on!, win);
        const tray = item.plant_out_on ? barStyle(item.sow_on!, item.plant_out_on, win) : null;
        const clash = over.includes(item.id!);
        const label = `${item.name}, ${item.area_m2} m², ${dayLabel(item.sow_on!)} to ${dayLabel(item.end_on!)}`;
        return (
          <div key={item.id} className="plan-row">
            <button type="button" className="plan-name link" onClick={() => onEdit(item)} title={label}>
              {item.name}
            </button>
            <div className="plan-track plan-bars">
              {tray && <span className="plan-bar tray" style={{ left: `${tray.left}%`, width: `${tray.width}%` }} aria-hidden />}
              {bar && (
                <button
                  type="button"
                  className={`plan-bar${item.method === "transplant" ? " transplant" : ""}${clash ? " clash" : ""}${item.status !== "planned" ? ` ${item.status}` : ""}${bar.clippedLeft ? " cut-left" : ""}${bar.clippedRight ? " cut-right" : ""}`}
                  style={{ left: `${bar.left}%`, width: `${bar.width}%` }}
                  onClick={() => onEdit(item)}
                  aria-label={`Edit ${label}`}
                >
                  <span>{item.area_m2} m²</span>
                </button>
              )}
            </div>
          </div>
        );
      })}
      {bookings.map((b) => {
        const bar = barStyle(b.starts_on!, b.ends_on!, win);
        if (!bar) return null;
        const label = `${b.equipment_name}${(b.quantity ?? 1) > 1 ? ` × ${b.quantity}` : ""}, ${dayLabel(b.starts_on!)} to ${dayLabel(b.ends_on!)}`;
        return (
          <div key={`eq-${b.id}`} className="plan-row plan-equipment">
            <span className="plan-name muted" title={label}>🔧 {b.equipment_name}</span>
            <div className="plan-track plan-bars">
              <span className="plan-bar equipment" style={{ left: `${bar.left}%`, width: `${bar.width}%` }} role="img" aria-label={`In use: ${label}`}>
                <span>{(b.quantity ?? 1) > 1 ? `× ${b.quantity}` : ""}</span>
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
