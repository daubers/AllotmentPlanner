import type { components } from "../api/schema";

export type Task = components["schemas"]["Task"];

export type Groups = { overdue: Task[]; today: Task[]; upcoming: Task[]; undated: Task[] };

const pad = (n: number) => String(n).padStart(2, "0");

/** Local calendar date as YYYY-MM-DD (due dates are plain dates, not instants). */
export function localDate(d: Date = new Date()): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function daysFrom(days: number, from: Date = new Date()): string {
  return localDate(new Date(from.getFullYear(), from.getMonth(), from.getDate() + days));
}

/** Open jobs bucketed by due date; the server already orders them by date then priority. */
export function groupTasks(tasks: Task[], today: string = localDate()): Groups {
  const g: Groups = { overdue: [], today: [], upcoming: [], undated: [] };
  for (const t of tasks) {
    if (t.status === "done") continue;
    if (!t.due_date) g.undated.push(t);
    else if (t.due_date < today) g.overdue.push(t);
    else if (t.due_date === today) g.today.push(t);
    else g.upcoming.push(t);
  }
  return g;
}

/** "Due today", "2 days late", "Tomorrow", "Due 12 Nov" or nothing. */
export function dueLabel(due: string | null | undefined, today: string = localDate()): string {
  if (!due) return "";
  const day = (s: string) => Date.UTC(+s.slice(0, 4), +s.slice(5, 7) - 1, +s.slice(8, 10));
  const diff = Math.round((day(due) - day(today)) / 86_400_000);
  if (diff === 0) return "Due today";
  if (diff === 1) return "Tomorrow";
  if (diff === -1) return "1 day late";
  if (diff < 0) return `${-diff} days late`;
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `Due ${+due.slice(8, 10)} ${months[+due.slice(5, 7) - 1]}`;
}

export type NewJob = {
  title: string;
  due_date?: string | null;
  priority?: "low" | "normal" | "high";
  feature_id?: number | null;
  location?: { lat: number; lng: number } | null;
};

const base = (allotmentId: number) => `/api/v1/allotments/${allotmentId}/tasks`;

/** The queued request that adds a job (sent when there is signal). */
export function createRequest(allotmentId: number, job: NewJob) {
  const body: Record<string, unknown> = { title: job.title.trim(), priority: job.priority ?? "normal" };
  if (job.due_date) body.due_date = job.due_date;
  if (job.feature_id != null) body.feature_id = job.feature_id;
  else if (job.location) body.location = { type: "Point", coordinates: [job.location.lng, job.location.lat] };
  return { method: "POST" as const, path: base(allotmentId), body };
}

/** Ticking a job is safe to send twice: the server treats it as already done. */
export function completeRequest(allotmentId: number, taskId: number) {
  return { method: "POST" as const, path: `${base(allotmentId)}/${taskId}/complete` };
}

export function reopenRequest(allotmentId: number, taskId: number) {
  return { method: "POST" as const, path: `${base(allotmentId)}/${taskId}/reopen` };
}

/** A job made on the phone before the server has given it an id: negative, so it never clashes. */
export function localJob(job: NewJob, now: number = Date.now()): Task {
  return {
    id: -now,
    title: job.title.trim(),
    description: "",
    status: "todo",
    priority: job.priority ?? "normal",
    due_date: job.due_date ?? null,
    feature_id: job.feature_id ?? null,
    location: null,
  } as Task;
}

/** The task list with one job ticked off or put back, as it should look before the server confirms. */
export function withStatus(tasks: Task[], taskId: number, status: "done" | "todo"): Task[] {
  return tasks.map((t) => (t.id === taskId ? { ...t, status } : t));
}
