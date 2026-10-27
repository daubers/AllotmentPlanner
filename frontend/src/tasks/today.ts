import type { Task } from "./group";

export type SheetFeature = { id: number; properties: { name?: string; kind?: string } };
export type Section = { title: string; tasks: Task[] };

/**
 * Group the day's jobs by where they are, so you can work through the plot bed by bed:
 * one section per pinned feature (in map order), then jobs pinned to a spot, then the rest.
 * Task order within a section is preserved (the server sorts by priority then date).
 */
export function groupByLocation(tasks: Task[], features: SheetFeature[]): Section[] {
  const byFeature = new Map<number, Task[]>();
  const pinned: Task[] = [];
  const anywhere: Task[] = [];
  for (const t of tasks) {
    if (t.feature_id != null) byFeature.set(t.feature_id, [...(byFeature.get(t.feature_id) ?? []), t]);
    else if (t.location) pinned.push(t);
    else anywhere.push(t);
  }
  const sections: Section[] = [];
  for (const f of features) {
    const list = byFeature.get(f.id);
    if (list) sections.push({ title: f.properties.name || `Unnamed ${f.properties.kind ?? "feature"}`, tasks: list });
  }
  // A task pinned to a feature we don't know about (shouldn't happen) is not lost.
  for (const [id, list] of byFeature) {
    if (!features.some((f) => f.id === id)) anywhere.push(...list);
  }
  if (pinned.length) sections.push({ title: "Pinned on the map", tasks: pinned });
  if (anywhere.length) sections.push({ title: "Anywhere", tasks: anywhere });
  return sections;
}

/** The printed order, which is also the numbering used on the sketch. */
export function flatten(sections: Section[]): Task[] {
  return sections.flatMap((s) => s.tasks);
}

const MS_PER_DAY = 86_400_000;

/** Whole days between two YYYY-MM-DD dates (b - a), independent of time zone and DST. */
export function daysBetween(a: string, b: string): number {
  const parse = (s: string) => Date.UTC(+s.slice(0, 4), +s.slice(5, 7) - 1, +s.slice(8, 10));
  return Math.round((parse(b) - parse(a)) / MS_PER_DAY);
}

export function longDate(iso: string): string {
  const d = new Date(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10));
  // Assembled from parts: Intl's separators (e.g. "Monday, 2 November") vary between ICU versions.
  const part = (type: Intl.DateTimeFormatPartTypes) =>
    new Intl.DateTimeFormat("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" })
      .formatToParts(d)
      .find((p) => p.type === type)!.value;
  return `${part("weekday")} ${part("day")} ${part("month")} ${part("year")}`;
}
