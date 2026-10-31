import { localDate, type Task } from "./group";

export type Sort = "due" | "priority" | "newest";
export type Filters = {
  q: string;
  /** "all", "me", "none" (unassigned) or a user id. */
  who: string;
  priority: "" | "low" | "normal" | "high";
  /** "feature:3", "tray:2", "planting:7" or "" for anywhere. */
  place: string;
  status: "all" | "todo" | "doing" | "done";
  sort: Sort;
};

export const DEFAULT_FILTERS: Filters = { q: "", who: "all", priority: "", place: "", status: "all", sort: "due" };

const SORTS: Sort[] = ["due", "priority", "newest"];
const STATUSES = ["all", "todo", "doing", "done"];
const PRIORITIES = ["", "low", "normal", "high"];
const RANK = { high: 0, normal: 1, low: 2 } as const;

/** The filters held in a page's query string; anything unrecognised falls back to its default. */
export function readFilters(params: URLSearchParams): Filters {
  const pick = <T extends string>(key: string, allowed: readonly string[], fallback: T) => {
    const v = params.get(key);
    return (v !== null && allowed.includes(v) ? v : fallback) as T;
  };
  return {
    q: params.get("q") ?? "",
    who: params.get("who") || DEFAULT_FILTERS.who,
    priority: pick("priority", PRIORITIES, DEFAULT_FILTERS.priority),
    place: params.get("place") ?? "",
    status: pick("status", STATUSES, DEFAULT_FILTERS.status),
    sort: pick("sort", SORTS, DEFAULT_FILTERS.sort),
  };
}

/** Query-string form of ``filters``: only what differs from the defaults, so the URL stays short. */
export function writeFilters(filters: Filters, into: URLSearchParams = new URLSearchParams()): URLSearchParams {
  const next = new URLSearchParams(into);
  for (const key of Object.keys(DEFAULT_FILTERS) as (keyof Filters)[]) {
    if (filters[key] === DEFAULT_FILTERS[key]) next.delete(key);
    else next.set(key, filters[key]);
  }
  return next;
}

export const isFiltered = (f: Filters): boolean =>
  (Object.keys(DEFAULT_FILTERS) as (keyof Filters)[]).some((k) => k !== "sort" && f[k] !== DEFAULT_FILTERS[k]);

const placeOf = (t: Task): string =>
  t.feature_id ? `feature:${t.feature_id}` : t.tray_id ? `tray:${t.tray_id}` : t.planting_id ? `planting:${t.planting_id}` : "";

/** ``tasks`` that match ``f``, in the order ``f.sort`` asks for. ``me`` is the signed-in user's id. */
export function filterTasks(tasks: Task[], f: Filters, me: number | null | undefined): Task[] {
  const words = f.q.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const kept = tasks.filter((t) => {
    if (f.status !== "all" && t.status !== f.status) return false;
    if (f.priority && t.priority !== f.priority) return false;
    if (f.place && placeOf(t) !== f.place) return false;
    if (f.who === "me" && (me == null || t.assignee_id !== me)) return false;
    if (f.who === "none" && t.assignee_id != null) return false;
    if (/^\d+$/.test(f.who) && t.assignee_id !== Number(f.who)) return false;
    const text = `${t.title} ${t.description ?? ""}`.toLowerCase();
    return words.every((w) => text.includes(w));
  });
  const due = (t: Task) => t.due_date ?? "9999-12-31";
  const byDue = (a: Task, b: Task) => due(a).localeCompare(due(b)) || a.id! - b.id!;
  const rank = (t: Task) => RANK[t.priority as keyof typeof RANK] ?? 1;
  if (f.sort === "priority") return kept.sort((a, b) => rank(a) - rank(b) || byDue(a, b));
  if (f.sort === "newest") return kept.sort((a, b) => b.id! - a.id!);
  return kept.sort((a, b) => byDue(a, b) || rank(a) - rank(b));
}

/** Common reschedule targets as YYYY-MM-DD, counted from ``from`` (local date). */
export function rescheduleDates(from: Date = new Date()): { tomorrow: string; nextWeek: string } {
  const plus = (days: number) => {
    const d = new Date(from.getFullYear(), from.getMonth(), from.getDate() + days);
    return localDate(d);
  };
  return { tomorrow: plus(1), nextWeek: plus(7) };
}
