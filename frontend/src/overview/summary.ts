import type { components } from "../api/schema";

export type Overview = components["schemas"]["Overview"];
export type OverviewDay = components["schemas"]["OverviewDay"];
type Counts = components["schemas"]["OverviewCounts"];

/** Heat level 0-4 for a day's activity relative to the busiest day in view. */
export function level(total: number, max: number): 0 | 1 | 2 | 3 | 4 {
  if (total <= 0 || max <= 0) return 0;
  return Math.min(4, Math.max(1, Math.ceil((total / max) * 4))) as 1 | 2 | 3 | 4;
}

/** Calendar columns, Monday first: each is one week of 7 slots, null where outside the data. */
export function weekColumns(days: OverviewDay[]): (OverviewDay | null)[][] {
  if (!days.length) return [];
  const lead = (new Date(`${days[0].date}T00:00:00Z`).getUTCDay() + 6) % 7; // Mon = 0
  const slots: (OverviewDay | null)[] = [...Array<null>(lead).fill(null), ...days];
  while (slots.length % 7) slots.push(null);
  const columns: (OverviewDay | null)[][] = [];
  for (let i = 0; i < slots.length; i += 7) columns.push(slots.slice(i, i + 7));
  return columns;
}

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

/** The encouraging one-liner for the week so far. */
export function weekHeadline(thisWeek: Counts, lastWeek: Counts): string {
  const parts: string[] = [];
  if (thisWeek.tasks_done) parts.push(`completed ${plural(thisWeek.tasks_done, "task")}`);
  if (thisWeek.photos_added) parts.push(`added ${plural(thisWeek.photos_added, "photo")}`);
  if (thisWeek.map_edits) parts.push(`made ${plural(thisWeek.map_edits, "map edit")}`);
  if (!parts.length) return "A fresh week: nothing logged yet. Pick one small job to start.";
  const text = parts.length > 1 ? `${parts.slice(0, -1).join(", ")} and ${parts.at(-1)}` : parts[0];
  const diff = (thisWeek.tasks_done ?? 0) - (lastWeek.tasks_done ?? 0);
  const trend = lastWeek.tasks_done && diff > 0 ? ` That's ${diff} more tasks than last week.` : "";
  return `This week you ${text}.${trend}`;
}

export function streakText(current: number, longest: number): string {
  if (!current) return longest ? `Best streak: ${plural(longest, "day")}. Start a new one today!` : "No streak yet";
  return current >= longest
    ? `${plural(current, "day")} in a row: your best yet!`
    : `${plural(current, "day")} in a row (best ${longest})`;
}

export function dayLabel(d: OverviewDay): string {
  const parts = new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" })
    .formatToParts(new Date(`${d.date}T00:00:00Z`)); // joined by hand: ICU versions disagree on the comma
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  const date = `${get("weekday")}, ${get("day")} ${get("month")}`;
  if (!d.total) return `${date}: nothing logged`;
  const bits = [
    d.tasks_done && plural(d.tasks_done, "task") + " done",
    d.photos_added && plural(d.photos_added, "photo"),
    d.map_edits && plural(d.map_edits, "map edit"),
    d.tasks_added && plural(d.tasks_added, "task") + " added",
  ].filter(Boolean);
  return `${date}: ${bits.join(", ")}`;
}
