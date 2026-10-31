import type { Planting } from "../plantings/hooks";
import type { TraySummary } from "../trays/grid";
import type { FeatureOption } from "./hooks";

/** The <option>s for choosing where a task is: a map shape, a seed tray or something growing. */
export default function PlaceOptions({
  features,
  trays,
  plantings,
}: {
  features?: FeatureOption[];
  trays?: TraySummary[];
  plantings?: Planting[];
}) {
  return (
    <>
      {features && features.length > 0 && (
        <optgroup label="Map">
          {features.map((f) => <option key={f.id} value={`feature:${f.id}`}>{f.name}</option>)}
        </optgroup>
      )}
      {trays && trays.length > 0 && (
        <optgroup label="Seed trays">
          {trays.map((t) => <option key={t.id} value={`tray:${t.id}`}>{t.name}</option>)}
        </optgroup>
      )}
      {plantings && plantings.length > 0 && (
        <optgroup label="Growing">
          {plantings.map((p) => (
            <option key={p.id} value={`planting:${p.id}`}>{p.packet_name || "Planting"} in {p.bed_name}</option>
          ))}
        </optgroup>
      )}
    </>
  );
}
