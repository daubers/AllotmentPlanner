import { MONTH_NAMES } from "../seeds/calendar";
import { addDays, fromDay, toDay } from "./dates";

export type MonthCell = { key: string; label: string; year: number; month: number; start: string; end: string };
/** `to` is the last day shown; each month's `end` is the first day of the next. */
export type Win = { key: string; from: string; to: string; months: MonthCell[] };

const KEY = /^(\d{4})-(0[1-9]|1[0-2])$/;

export const monthKeyOf = (iso: string): string => iso.slice(0, 7);
export const currentKey = (now = new Date()): string => `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
export const parseKey = (value: string | null, fallback: string): string => (value && KEY.test(value) ? value : fallback);

export function shiftMonth(key: string, by: number): string {
  const [y, m] = key.split("-").map(Number);
  const index = y * 12 + (m - 1) + by;
  return `${Math.floor(index / 12)}-${String((index % 12) + 1).padStart(2, "0")}`;
}

/** Twelve months from the first of `key`. */
export function makeWindow(key: string): Win {
  const months: MonthCell[] = [];
  for (let i = 0; i < 12; i++) {
    const k = shiftMonth(key, i);
    const [year, month] = k.split("-").map(Number);
    months.push({ key: k, label: MONTH_NAMES[month - 1], year, month, start: `${k}-01`, end: `${shiftMonth(k, 1)}-01` });
  }
  return { key, from: months[0].start, to: addDays(months[11].end, -1), months };
}

export type Bar = { left: number; width: number; clippedLeft: boolean; clippedRight: boolean };

/** Where a stretch of time [start, end) sits in the window, as percentages; null if it is outside it. */
export function barStyle(start: string, end: string, win: Win): Bar | null {
  const w0 = toDay(win.from);
  const w1 = toDay(win.to) + 1;
  const s = Math.max(toDay(start), w0);
  const e = Math.min(toDay(end), w1);
  if (e <= s) return null;
  const total = w1 - w0;
  return {
    left: ((s - w0) / total) * 100,
    width: ((e - s) / total) * 100,
    clippedLeft: toDay(start) < w0,
    clippedRight: toDay(end) > w1,
  };
}

type Occupier = { area_m2?: number; sow_on?: string; plant_out_on?: string | null; end_on?: string; status?: string };

/** The most space in use on any one day of each month, in the window's month order. */
export function peakUsage(items: Occupier[], win: Win): number[] {
  const live = items
    .filter((i) => i.status !== "skipped" && i.sow_on && i.end_on)
    .map((i) => ({ area: i.area_m2 ?? 0, from: toDay(i.plant_out_on ?? i.sow_on!), to: toDay(i.end_on!) }));
  return win.months.map((m) => {
    let peak = 0;
    for (let d = toDay(m.start); d < toDay(m.end); d++) {
      let used = 0;
      for (const i of live) if (i.from <= d && d < i.to) used += i.area;
      if (used > peak) peak = used;
    }
    return Math.round(peak * 100) / 100;
  });
}

export const dayLabel = (iso: string): string => {
  const [, m, d] = iso.split("-").map(Number);
  return `${d} ${MONTH_NAMES[m - 1]}`;
};
export { fromDay };
