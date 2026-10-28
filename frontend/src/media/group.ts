import type { components } from "../api/schema";

export type Media = components["schemas"]["Media"];

export type Day = { date: string; items: Media[] };

/** The calendar day a photo belongs to. Times are shown in UTC throughout so grouping is stable. */
export function dayOf(m: Media): string {
  return (m.taken_at ?? "").slice(0, 10);
}

/** Group by day, newest day first; within a day, in the order given (the API sorts by time). */
export function groupByDay(items: Media[], newestFirst = true): Day[] {
  const days = new Map<string, Media[]>();
  for (const m of items) days.set(dayOf(m), [...(days.get(dayOf(m)) ?? []), m]);
  const sorted = [...days.entries()].sort(([a], [b]) => (newestFirst ? b.localeCompare(a) : a.localeCompare(b)));
  return sorted.map(([date, list]) => ({ date, items: list }));
}

export function timeOf(m: Media): string {
  return new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "UTC" }).format(new Date(m.taken_at!));
}

export function mapLink(m: Media): string | null {
  return m.lat != null && m.lng != null ? `https://www.openstreetmap.org/?mlat=${m.lat}&mlon=${m.lng}#map=19/${m.lat}/${m.lng}` : null;
}

export function compass(heading: number | null | undefined): string | null {
  if (heading == null) return null;
  const names = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
  return names[Math.round((((heading % 360) + 360) % 360) / 45) % 8];
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return "";
  const s = Math.round(seconds);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
}
