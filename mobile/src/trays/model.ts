/** Pure helpers for the tray grid on the phone (the same rules as the web grid). */
export type Cell = { row: number; col: number; packet_id?: number | null; count?: number | null; status?: string; note?: string };
export type Counts = { empty?: number; sown?: number; germinated?: number; failed?: number; planted_out?: number };

export const key = (row: number, col: number): string => `${row},${col}`;
export const posOf = (k: string): { row: number; col: number } => {
  const [row, col] = k.split(",").map(Number);
  return { row, col };
};

export function toggle(sel: ReadonlySet<string>, k: string): Set<string> {
  const next = new Set(sel);
  if (!next.delete(k)) next.add(k);
  return next;
}

function group(sel: ReadonlySet<string>, keys: string[]): Set<string> {
  const next = new Set(sel);
  if (keys.every((k) => next.has(k))) keys.forEach((k) => next.delete(k));
  else keys.forEach((k) => next.add(k));
  return next;
}
export const toggleRow = (sel: ReadonlySet<string>, row: number, cols: number) => group(sel, Array.from({ length: cols }, (_, c) => key(row, c)));
export const toggleCol = (sel: ReadonlySet<string>, col: number, rows: number) => group(sel, Array.from({ length: rows }, (_, r) => key(r, col)));

export const cellMap = (cells: Cell[] = []): Map<string, Cell> => new Map(cells.map((c) => [key(c.row, c.col), c]));

export const STATUS_LABEL: Record<string, string> = { empty: "empty", sown: "sown", germinated: "came up", failed: "failed", planted_out: "planted out" };

/** "5 sown, 2 came up, 4 empty" (zero counts left out). */
export function summarise(counts: Counts | undefined): string {
  if (!counts) return "";
  return (["sown", "germinated", "failed", "planted_out", "empty"] as const)
    .filter((s) => (counts[s] ?? 0) > 0)
    .map((s) => `${counts[s]} ${STATUS_LABEL[s]}`)
    .join(", ");
}

export function describeCell(row: number, col: number, cell: Cell | undefined, packetName?: string): string {
  const where = `Row ${row + 1}, column ${col + 1}`;
  return cell ? `${where}: ${packetName || "unknown seed"}, ${STATUS_LABEL[cell.status ?? "sown"]}` : `${where}: empty`;
}

/** The glyph shown in a cell: a tick when it came up, a cross when it failed, else the seed count. */
export function glyph(cell: Cell | undefined): string {
  if (!cell) return "";
  if (cell.status === "germinated") return "✓";
  if (cell.status === "failed") return "✕";
  if (cell.status === "planted_out") return "↗";
  return cell.count ? String(cell.count) : "";
}

export const KIND_COLOURS = ["#cfe8c9", "#f6dca4", "#bcd9ee", "#f1c0bd", "#dcc9ea", "#c5e6e2", "#eadfb8", "#d8d8d8"];
export function colourFor(packetId: number | null | undefined, kinds: { packet_id?: number }[] = []): string | null {
  if (packetId == null) return null;
  const i = kinds.findIndex((k) => k.packet_id === packetId);
  return i < 0 ? null : KIND_COLOURS[i % KIND_COLOURS.length];
}

export type CellChange = { status?: "sown" | "germinated" | "failed" | "empty"; packet_id?: number; count?: number; note?: string };

/** The queued request for a change to the chosen cells (sent when there is signal, oldest first). */
export function cellsRequest(trayId: number, allotmentId: number, selected: ReadonlySet<string>, set: CellChange) {
  return {
    method: "PATCH" as const,
    path: `/api/v1/allotments/${allotmentId}/trays/${trayId}/cells`,
    body: { cells: [...selected].map(posOf), set },
  };
}

/** Apply a change to a tray's cached cells straight away, so the screen answers before the server does. */
export function applyLocally(cells: Cell[], selected: ReadonlySet<string>, set: CellChange): Cell[] {
  const byKey = cellMap(cells);
  for (const k of selected) {
    const { row, col } = posOf(k);
    const cur = byKey.get(k);
    if (set.status === "empty") {
      byKey.delete(k);
      continue;
    }
    if (!cur && (set.status === "germinated" || set.status === "failed")) continue; // nothing sown there
    const next: Cell = { ...(cur ?? { row, col, status: "sown", count: 1 }) };
    if (set.packet_id !== undefined) next.packet_id = set.packet_id;
    if (set.count !== undefined) next.count = set.count;
    if (set.note !== undefined) next.note = set.note;
    if (set.status) next.status = set.status;
    if (cur?.status === "planted_out") continue;
    byKey.set(k, next);
  }
  return [...byKey.values()].sort((a, b) => a.row - b.row || a.col - b.col);
}

/** How many cells are in each state; every cell with no row is empty. */
export function countsOf(rows: number, cols: number, cells: Cell[]): Required<Counts> {
  const counts = { empty: rows * cols, sown: 0, germinated: 0, failed: 0, planted_out: 0 };
  for (const c of cells) {
    const status = (c.status ?? "sown") as keyof typeof counts;
    if (status in counts && status !== "empty") counts[status] += 1;
    counts.empty -= 1;
  }
  return counts;
}
