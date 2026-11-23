/** Combine a YYYY-MM-DD date and HH:MM time, both read in the phone's local timezone, into a
 *  UTC ISO instant for the API. Returns null if either doesn't parse. */
export function combineLocalDateTime(date: string, time: string): string | null {
  const d = new Date(`${date}T${time || "09:00"}`);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

type Bring = { name?: string; source?: string; status?: string };

/** One line of a visit's bring list: its name, and whether it was only suggested or is out of action. */
export function bringLabel(item: Bring): string {
  const notes = [item.source === "suggested" ? "suggested" : "", item.status === "out_of_action" ? "out of action" : ""].filter(Boolean);
  return notes.length ? `${item.name ?? "Equipment"} (${notes.join(", ")})` : (item.name ?? "Equipment");
}
