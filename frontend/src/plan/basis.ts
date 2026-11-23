import type { components } from "../api/schema";
import type { Spacing } from "./area";
import { addDays, nextInWindow } from "./dates";

export type Crop = components["schemas"]["Crop"];
export type Packet = components["schemas"]["Packet"];
export type Method = "direct_sow" | "transplant";

/** Everything a plan item needs to know about what is being grown, from a packet or a built-in crop. */
export type Basis = {
  name: string;
  cropKey: string | null;
  packetId: number | null;
  method: Method;
  spacing: Spacing;
  sowMonths: number[];
  plantOutMonths: number[];
  maturityMin: number;
  maturityMax: number;
  successionDays: number | null;
};

export const TRAY_DAYS = 28; // how long a transplant spends in a tray before it goes out
const DEFAULT_MATURITY = [60, 90] as const;

export function basisFromCrop(c: Crop): Basis {
  return {
    name: c.name ?? "",
    cropKey: c.key ?? null,
    packetId: null,
    method: c.method_default ?? "direct_sow",
    spacing: { plant: c.spacing_plant_cm ?? null, row: c.spacing_row_cm ?? null },
    sowMonths: c.sow_months ?? [],
    plantOutMonths: c.plant_out_months ?? [],
    maturityMin: c.maturity_days_min ?? DEFAULT_MATURITY[0],
    maturityMax: c.maturity_days_max ?? DEFAULT_MATURITY[1],
    successionDays: c.succession_days ?? null,
  };
}

/** A packet's own figures; whatever it leaves blank falls back to `crop` (if given) or a plain default. */
export function basisFromPacket(p: Packet, crop?: Crop | null): Basis {
  const cal = p.calendar ?? {};
  const indoors = cal.sow_indoors ?? [];
  const outdoors = cal.sow_outdoors ?? [];
  const transplant = indoors.length > 0 && outdoors.length === 0;
  const base = crop ? basisFromCrop(crop) : null;
  const sow = transplant ? indoors : outdoors.length ? outdoors : indoors;
  return {
    name: p.variety ? `${p.name} (${p.variety})` : (p.name ?? ""),
    cropKey: base?.cropKey ?? null,
    packetId: p.id ?? null,
    method: sow.length ? (transplant ? "transplant" : "direct_sow") : (base?.method ?? "direct_sow"),
    spacing: {
      plant: p.spacing_plant_cm ?? base?.spacing.plant ?? null,
      row: p.spacing_row_cm ?? base?.spacing.row ?? null,
    },
    sowMonths: sow.length ? sow : (base?.sowMonths ?? []),
    plantOutMonths: cal.plant_out?.length ? cal.plant_out : (base?.plantOutMonths ?? []),
    maturityMin: p.maturity_days_min ?? base?.maturityMin ?? DEFAULT_MATURITY[0],
    maturityMax: p.maturity_days_max ?? base?.maturityMax ?? DEFAULT_MATURITY[1],
    successionDays: base?.successionDays ?? null,
  };
}

export type Dates = { sow_on: string; plant_out_on: string | null; end_on: string };

/** Sensible dates for starting `b` from `today`: the next sowing month, then out and cleared in time. */
export function defaultDates(b: Basis, today: string): Dates {
  const sow = nextInWindow(b.sowMonths, today) ?? today;
  if (b.method === "direct_sow") return { sow_on: sow, plant_out_on: null, end_on: addDays(sow, b.maturityMax) };
  const earliest = addDays(sow, TRAY_DAYS);
  const out = nextInWindow(b.plantOutMonths, earliest) ?? earliest;
  const end = addDays(sow, b.maturityMax);
  const minimum = addDays(out, 30);
  return { sow_on: sow, plant_out_on: out, end_on: end > minimum ? end : minimum };
}
