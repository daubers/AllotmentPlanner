/** Pure helpers for the seed library screens. */
export const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export const ACTIVITIES = [
  { key: "sow_indoors", label: "Sow indoors" },
  { key: "sow_outdoors", label: "Sow outdoors" },
  { key: "plant_out", label: "Plant out" },
  { key: "harvest", label: "Harvest" },
] as const;
export type Activity = (typeof ACTIVITIES)[number]["key"];
export type Calendar = Partial<Record<Activity, number[]>>;

export const STOCK_LABEL: Record<string, string> = { full: "Full", part: "Part used", low: "Running low", empty: "Empty" };

export type PacketLike = {
  id?: number;
  name?: string;
  variety?: string;
  supplier?: string;
  latin_name?: string;
  notes?: string;
  calendar?: Calendar;
};

export const currentMonth = (now = new Date()): number => now.getMonth() + 1;

export function toggleMonth(months: number[] = [], month: number): number[] {
  return months.includes(month) ? months.filter((m) => m !== month) : [...months, month].sort((a, b) => a - b);
}

/** "Mar to May, Sep": runs of months joined up, carrying over the new year (Nov to Feb). */
export function monthsLabel(months: number[] = []): string {
  const set = new Set(months);
  if (set.size === 0) return "";
  if (set.size === 12) return "All year";
  const starts = [...set].filter((m) => !set.has(m === 1 ? 12 : m - 1)).sort((a, b) => a - b);
  return starts
    .map((start) => {
      let end = start;
      while (set.has(end === 12 ? 1 : end + 1)) end = end === 12 ? 1 : end + 1;
      return start === end ? MONTH_NAMES[start - 1] : `${MONTH_NAMES[start - 1]} to ${MONTH_NAMES[end - 1]}`;
    })
    .join(", ");
}

/** Whether a packet can be sown (indoors or out) in the month. */
export function sowableIn(packet: PacketLike, month: number): boolean {
  const c = packet.calendar ?? {};
  return !!c.sow_indoors?.includes(month) || !!c.sow_outdoors?.includes(month);
}

/** Search the library the way the web does: any of name, variety, supplier, latin name, notes. */
export function filterPackets<P extends PacketLike>(packets: P[], { q = "", month }: { q?: string; month?: number | null } = {}): P[] {
  const needle = q.trim().toLowerCase();
  return packets.filter((p) => {
    if (month != null && !sowableIn(p, month)) return false;
    if (!needle) return true;
    return [p.name, p.variety, p.supplier, p.latin_name, p.notes].some((v) => (v ?? "").toLowerCase().includes(needle));
  });
}

export const packetTitle = (p: PacketLike): string => (p.variety ? `${p.name} (${p.variety})` : (p.name ?? "Packet"));

export function daysLabel(min?: number | null, max?: number | null): string {
  if (min == null && max == null) return "";
  if (min == null || max == null || min === max) return `${min ?? max} days`;
  return `${min} to ${max} days`;
}

/** Form fields the phone sends with a photo to have it read as the back of a seed packet. */
export function scanFields(clientId: string): Record<string, string> {
  return { read_packet: "true", client_id: clientId };
}

/** Fields that tell the server a photo belongs to a packet, tray, planting or task. */
export function photoFields(target: { packetId?: number; trayId?: number; plantingId?: number; taskId?: number }, clientId: string): Record<string, string> {
  const fields: Record<string, string> = { client_id: clientId };
  if (target.packetId != null) fields.packet_id = String(target.packetId);
  if (target.trayId != null) fields.tray_id = String(target.trayId);
  if (target.plantingId != null) fields.planting_id = String(target.plantingId);
  if (target.taskId != null) fields.task_id = String(target.taskId);
  return fields;
}
