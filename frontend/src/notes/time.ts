const pad = (n: number) => String(n).padStart(2, "0");

/** The local calendar day of a timestamp, as YYYY-MM-DD. */
export function dayOfNote(iso: string): string {
  const d = new Date(iso);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** Local time of day, e.g. 09:30. */
export function timeOfNote(iso: string): string {
  const d = new Date(iso);
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** A timestamp as the value of a datetime-local input (local time, no zone). */
export function toInput(iso: string): string {
  return `${dayOfNote(iso)}T${timeOfNote(iso)}`;
}

/** The value of a datetime-local input as an ISO instant. */
export function fromInput(value: string): string {
  return new Date(value).toISOString();
}

export type NoteDay<T> = { date: string; items: T[] };

/** Group by local day, newest day first; within a day, in the order given. */
export function groupNotesByDay<T extends { noted_at?: string }>(notes: T[]): NoteDay<T>[] {
  const days = new Map<string, T[]>();
  for (const n of notes) {
    const day = dayOfNote(n.noted_at ?? "");
    days.set(day, [...(days.get(day) ?? []), n]);
  }
  return [...days.entries()].sort(([a], [b]) => b.localeCompare(a)).map(([date, items]) => ({ date, items }));
}
