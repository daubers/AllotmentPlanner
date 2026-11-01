/** "3 min ago", "2 h ago": how long before `now` a time was, for the admin tables. */
export function ago(iso: string | null | undefined, now: number = Date.now()): string {
  if (!iso) return "never";
  const seconds = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (seconds < 10) return "just now";
  if (seconds < 90) return `${seconds} s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 90) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours} h ago`;
  return `${Math.round(hours / 24)} days ago`;
}

/** "45 s", "12 min", "3 h 05 min": a length of time. */
export function duration(seconds: number | null | undefined): string {
  if (seconds == null) return "–";
  const s = Math.round(seconds);
  if (s < 90) return `${s} s`;
  const minutes = Math.round(s / 60);
  if (minutes < 90) return `${minutes} min`;
  return `${Math.floor(minutes / 60)} h ${String(minutes % 60).padStart(2, "0")} min`;
}

/** How long a job took, or has been going, from its timestamps. */
export function jobTime(job: { started_at?: string | null; finished_at?: string | null; created_at?: string }, now: number = Date.now()): number | null {
  const start = job.started_at ?? null;
  if (!start) return null;
  const end = job.finished_at ? new Date(job.finished_at).getTime() : now;
  return (end - new Date(start).getTime()) / 1000;
}
