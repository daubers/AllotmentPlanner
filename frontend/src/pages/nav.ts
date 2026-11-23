/** The allotment menu: pages grouped by the job you are doing. `to` is relative to /allotments/:id. */
export type NavPage = { to: string; label: string; end?: boolean };
export type NavGroup = { key: string; label: string; pages: NavPage[] };

export const NAV: NavGroup[] = [
  { key: "plot", label: "Plot", pages: [{ to: "", label: "Map", end: true }, { to: "layers", label: "Map from photos" }] },
  { key: "grow", label: "Grow", pages: [{ to: "seeds", label: "Seeds" }, { to: "trays", label: "Trays" }, { to: "beds", label: "Beds" }, { to: "plan", label: "Plan" }, { to: "equipment", label: "Equipment" }] },
  { key: "work", label: "Work", pages: [{ to: "today", label: "Today" }, { to: "tasks", label: "Tasks" }, { to: "visits", label: "Visits" }] },
  { key: "record", label: "Record", pages: [{ to: "photos", label: "Photos" }, { to: "notes", label: "Notes" }, { to: "overview", label: "Overview" }] },
];

/** The first path segment after /allotments/:id ("" for the map itself). */
export function sectionOf(pathname: string): string {
  return /^\/allotments\/[^/]+\/?([^/]*)/.exec(pathname)?.[1] ?? "";
}

/** Which group a URL belongs to. Detail pages (a packet, a bed, a tray) stay with their list; Settings
 *  belongs to none; anything unknown falls back to the first group. */
export function groupFor(pathname: string): string | null {
  const section = sectionOf(pathname);
  if (section === "settings") return null;
  return NAV.find((g) => g.pages.some((p) => p.to === section))?.key ?? NAV[0].key;
}
