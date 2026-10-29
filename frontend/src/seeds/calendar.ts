export const ACTIVITIES = [
  { key: "sow_indoors", label: "Sow indoors" },
  { key: "sow_outdoors", label: "Sow outdoors" },
  { key: "plant_out", label: "Plant out" },
  { key: "harvest", label: "Harvest" },
] as const;

export type Activity = (typeof ACTIVITIES)[number]["key"];
export type Calendar = Partial<Record<Activity, number[]>>;

export const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export const STOCK = [
  ["full", "Full"],
  ["part", "Part used"],
  ["low", "Running low"],
  ["empty", "Empty"],
] as const;

export type StockLevel = (typeof STOCK)[number][0];

export const SUN = [
  ["full", "Full sun"],
  ["partial", "Part shade"],
  ["shade", "Shade"],
] as const;

export const currentMonth = (now = new Date()): number => now.getMonth() + 1;

/** Add the month if missing, remove it if present; always sorted. */
export function toggleMonth(months: number[] = [], month: number): number[] {
  return months.includes(month) ? months.filter((m) => m !== month) : [...months, month].sort((a, b) => a - b);
}

/** "Mar to May, Sep": runs of months joined up. A run may carry over the new year (Nov to Feb). */
export function monthsLabel(months: number[] = []): string {
  const set = new Set(months);
  if (set.size === 0) return "";
  if (set.size === 12) return "All year";
  // Start each run at a month whose predecessor (wrapping) is absent.
  const starts = [...set].filter((m) => !set.has(m === 1 ? 12 : m - 1)).sort((a, b) => a - b);
  return starts
    .map((start) => {
      let end = start;
      while (set.has(end === 12 ? 1 : end + 1)) end = end === 12 ? 1 : end + 1;
      return start === end ? MONTH_NAMES[start - 1] : `${MONTH_NAMES[start - 1]} to ${MONTH_NAMES[end - 1]}`;
    })
    .join(", ");
}

/** "7 to 14 days", "10 days", or "" when neither is known. */
export function daysLabel(min?: number | null, max?: number | null): string {
  if (min == null && max == null) return "";
  if (min == null || max == null || min === max) return `${min ?? max} days`;
  return `${min} to ${max} days`;
}
