/** Combine a YYYY-MM-DD date and HH:MM time, both read in the phone's local timezone, into a
 *  UTC ISO instant for the API. Returns null if either doesn't parse. */
export function combineLocalDateTime(date: string, time: string): string | null {
  const d = new Date(`${date}T${time || "09:00"}`);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}
