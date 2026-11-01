import type { components } from "../api/schema";

export type Tray = components["schemas"]["Tray"];
export type TraySummary = components["schemas"]["TraySummary"];
export type TrayCell = components["schemas"]["TrayCell"];
export type Counts = components["schemas"]["TrayCounts"];

export type Pos = { row: number; col: number };

/** Cells are picked as a set of "row,col" keys so toggling and set maths stay simple. */
export const key = (row: number, col: number): string => `${row},${col}`;
export const posOf = (k: string): Pos => {
  const [row, col] = k.split(",").map(Number);
  return { row, col };
};

export function toggle(sel: ReadonlySet<string>, k: string): Set<string> {
  const next = new Set(sel);
  if (!next.delete(k)) next.add(k);
  return next;
}

/** Click a row label: select the whole row, or deselect it if it is already all selected. */
export function toggleRow(sel: ReadonlySet<string>, row: number, cols: number): Set<string> {
  const keys = Array.from({ length: cols }, (_, c) => key(row, c));
  return toggleGroup(sel, keys);
}

export function toggleCol(sel: ReadonlySet<string>, col: number, rows: number): Set<string> {
  const keys = Array.from({ length: rows }, (_, r) => key(r, col));
  return toggleGroup(sel, keys);
}

function toggleGroup(sel: ReadonlySet<string>, keys: string[]): Set<string> {
  const next = new Set(sel);
  if (keys.every((k) => next.has(k))) keys.forEach((k) => next.delete(k));
  else keys.forEach((k) => next.add(k));
  return next;
}

export function selectAll(rows: number, cols: number): Set<string> {
  return new Set(Array.from({ length: rows * cols }, (_, i) => key(Math.floor(i / cols), i % cols)));
}

export function cellMap(cells: TrayCell[] = []): Map<string, TrayCell> {
  return new Map(cells.map((c) => [key(c.row!, c.col!), c]));
}

/** Where a kind of seed sits in the palette: the same packet always gets the same colour in a tray. */
export const PALETTE_SIZE = 8;
export function colourIndex(packetId: number | null | undefined, kinds: { packet_id?: number }[] = []): number {
  if (packetId == null) return -1;
  const i = kinds.findIndex((k) => k.packet_id === packetId);
  return i < 0 ? -1 : i % PALETTE_SIZE;
}

export const STATUS_LABEL: Record<string, string> = {
  empty: "empty",
  sown: "sown",
  germinated: "germinated",
  failed: "failed",
  planted_out: "planted out",
};

/** "5 sown, 2 germinated, 4 empty" (zero counts left out). */
export function summarise(counts: Counts | undefined): string {
  if (!counts) return "";
  const order = ["sown", "germinated", "failed", "planted_out", "empty"] as const;
  return order
    .filter((s) => (counts[s] ?? 0) > 0)
    .map((s) => `${counts[s]} ${STATUS_LABEL[s]}`)
    .join(", ");
}

export function describeCell(row: number, col: number, cell: TrayCell | undefined, packetName?: string): string {
  const where = `Row ${row + 1}, column ${col + 1}`;
  if (!cell) return `${where}: empty`;
  return `${where}: ${packetName || "unknown seed"}, ${STATUS_LABEL[cell.status ?? "sown"]}`;
}

/** Days between an ISO date and today (positive = in the past), for "sown 12 days ago". */
export function daysSince(iso: string | null | undefined, now = new Date()): number | null {
  if (!iso) return null;
  const then = new Date(`${iso}T00:00:00`);
  return Math.round((new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime() - then.getTime()) / 86_400_000);
}

/**
 * What the picked cells hold now, in words, so an edit can say what it will change:
 * "2 sown with Tomato, 3 seeds each, sown 2026-03-01; 1 empty". Empty when nothing is picked.
 */
export function describeSelection(selected: ReadonlySet<string>, cells: ReadonlyMap<string, TrayCell>, nameOf: (id?: number | null) => string | undefined): string {
  const picked = [...selected].map((k) => cells.get(k));
  const held = picked.filter((c): c is TrayCell => !!c);
  const empty = picked.length - held.length;
  const parts: string[] = [];
  if (held.length > 0) {
    const same = <T,>(values: T[]): T | "mixed" => (values.every((v) => v === values[0]) ? values[0] : "mixed");
    const packet = same(held.map((c) => c.packet_id ?? null));
    const count = same(held.map((c) => c.count ?? null));
    const sown = same(held.map((c) => c.sown_on ?? null));
    const kind = packet === "mixed" ? "different seeds" : packet == null ? "unknown seed" : nameOf(packet) ?? "unknown seed";
    const seeds = count === "mixed" ? "different numbers of seeds" : count == null ? "" : `${count} seed${count === 1 ? "" : "s"} each`;
    const date = sown === "mixed" ? "sown on different dates" : sown == null ? "" : `sown ${sown}`;
    parts.push(`${held.length} with ${[kind, seeds, date].filter(Boolean).join(", ")}`);
  }
  if (empty > 0) parts.push(`${empty} empty`);
  return parts.join("; ");
}
