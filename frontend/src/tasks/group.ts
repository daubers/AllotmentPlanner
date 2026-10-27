import type { components } from "../api/schema";

export type Task = components["schemas"]["Task"];

export type Groups = {
  overdue: Task[];
  today: Task[];
  upcoming: Task[];
  undated: Task[];
  done: Task[];
};

/** Local calendar date as YYYY-MM-DD (due dates are plain dates, not instants). */
export function localDate(d: Date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function groupTasks(tasks: Task[], today: string = localDate()): Groups {
  const groups: Groups = { overdue: [], today: [], upcoming: [], undated: [], done: [] };
  for (const t of tasks) {
    if (t.status === "done") groups.done.push(t);
    else if (!t.due_date) groups.undated.push(t);
    else if (t.due_date < today) groups.overdue.push(t);
    else if (t.due_date === today) groups.today.push(t);
    else groups.upcoming.push(t);
  }
  groups.done.sort((a, b) => (b.completed_at ?? "").localeCompare(a.completed_at ?? ""));
  return groups;
}
