/** Date-only maths on YYYY-MM-DD strings, in whole days, with no timezone surprises. */

export const toDay = (iso: string): number => {
  const [y, m, d] = iso.split("-").map(Number);
  return Date.UTC(y, m - 1, d) / 86_400_000;
};

export const fromDay = (day: number): string => new Date(day * 86_400_000).toISOString().slice(0, 10);

export const addDays = (iso: string, days: number): string => fromDay(toDay(iso) + days);

/** Today as the browser's local YYYY-MM-DD. */
export function todayISO(now = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/** The first day on or after `on` that falls in one of `months` (1 to 12); the year may roll over. */
export function nextInWindow(months: number[] | null | undefined, on: string): string | null {
  if (!months?.length) return null;
  const wanted = new Set(months);
  let [year, month] = on.split("-").map(Number);
  if (wanted.has(month)) return on;
  for (let i = 0; i < 12; i++) {
    month = (month % 12) + 1;
    if (month === 1) year += 1;
    if (wanted.has(month)) return `${year}-${String(month).padStart(2, "0")}-01`;
  }
  return null;
}
