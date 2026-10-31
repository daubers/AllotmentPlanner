import type { Task } from "./group";

export type SheetFeature = { id: number; properties: { name?: string; kind?: string } };
export type Section = {
  title: string;
  tasks: Task[];
  /** Where the heading links to, relative to the allotment (a bed, tray or planting's bed). */
  to?: string;
};
/** Names for tray and planting jobs, and which map shapes are beds (they have a page of their own). */
export type Places = {
  trays: { id: number; name: string }[];
  plantings: { id: number; label: string; feature_id: number }[];
};

/**
 * Group the day's jobs by where they are, so you can work through the plot bed by bed:
 * one section per pinned feature (in map order), then jobs pinned to a spot, then the rest.
 * Task order within a section is preserved (the server sorts by priority then date).
 */
export function groupByLocation(tasks: Task[], features: SheetFeature[], places: Places = { trays: [], plantings: [] }): Section[] {
  const byFeature = new Map<number, Task[]>();
  const byTray = new Map<number, Task[]>();
  const byPlanting = new Map<number, Task[]>();
  const pinned: Task[] = [];
  const anywhere: Task[] = [];
  const add = (map: Map<number, Task[]>, key: number, t: Task) => map.set(key, [...(map.get(key) ?? []), t]);
  for (const t of tasks) {
    if (t.feature_id != null) add(byFeature, t.feature_id, t);
    else if (t.tray_id != null) add(byTray, t.tray_id, t);
    else if (t.planting_id != null) add(byPlanting, t.planting_id, t);
    else if (t.location) pinned.push(t);
    else anywhere.push(t);
  }
  const sections: Section[] = [];
  for (const f of features) {
    const list = byFeature.get(f.id);
    if (list)
      sections.push({
        title: f.properties.name || `Unnamed ${f.properties.kind ?? "feature"}`,
        tasks: list,
        to: f.properties.kind === "bed" ? `beds/${f.id}` : undefined,
      });
  }
  for (const [id, list] of byTray) {
    const tray = places.trays.find((t) => t.id === id);
    if (tray) sections.push({ title: `Tray: ${tray.name}`, tasks: list, to: `trays/${id}` });
    else anywhere.push(...list);
  }
  for (const [id, list] of byPlanting) {
    const planting = places.plantings.find((p) => p.id === id);
    if (planting) sections.push({ title: planting.label, tasks: list, to: `beds/${planting.feature_id}` });
    else anywhere.push(...list);
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
