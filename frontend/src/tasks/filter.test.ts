import { describe, expect, it } from "vitest";
import { DEFAULT_FILTERS, filterTasks, isFiltered, readFilters, rescheduleDates, writeFilters, type Filters } from "./filter";
import type { Task } from "./group";

const t = (id: number, extra: Partial<Task>): Task =>
  ({ id, title: `Task ${id}`, description: "", status: "todo", priority: "normal", ...extra }) as Task;
const f = (extra: Partial<Filters>): Filters => ({ ...DEFAULT_FILTERS, ...extra });
const ids = (list: Task[]) => list.map((x) => x.id);

const tasks = [
  t(1, { title: "Water the beans", priority: "high", due_date: "2026-11-03", assignee_id: 1, feature_id: 5 }),
  t(2, { title: "Prune", description: "the old BEANS row", priority: "low", due_date: "2026-11-01", assignee_id: 2 }),
  t(3, { title: "Weed", status: "doing", tray_id: 8 }),
  t(4, { title: "Harvest", status: "done", priority: "high", assignee_id: 1, planting_id: 3, due_date: "2026-10-20" }),
];

describe("filterTasks", () => {
  it("keeps everything by default, in date order with undated last", () => {
    expect(ids(filterTasks(tasks, DEFAULT_FILTERS, 1))).toEqual([4, 2, 1, 3]);
  });

  it("searches the title and notes for every word, ignoring case", () => {
    expect(ids(filterTasks(tasks, f({ q: "beans" }), 1))).toEqual([2, 1]);
    expect(ids(filterTasks(tasks, f({ q: "OLD beans" }), 1))).toEqual([2]);
    expect(ids(filterTasks(tasks, f({ q: "water pruning" }), 1))).toEqual([]);
  });

  it("filters by assignee: me, unassigned or a person", () => {
    expect(ids(filterTasks(tasks, f({ who: "me" }), 1))).toEqual([4, 1]);
    expect(ids(filterTasks(tasks, f({ who: "me" }), null))).toEqual([]);
    expect(ids(filterTasks(tasks, f({ who: "none" }), 1))).toEqual([3]);
    expect(ids(filterTasks(tasks, f({ who: "2" }), 1))).toEqual([2]);
  });

  it("filters by priority, status and place", () => {
    expect(ids(filterTasks(tasks, f({ priority: "high" }), 1))).toEqual([4, 1]);
    expect(ids(filterTasks(tasks, f({ status: "doing" }), 1))).toEqual([3]);
    expect(ids(filterTasks(tasks, f({ status: "done" }), 1))).toEqual([4]);
    expect(ids(filterTasks(tasks, f({ place: "feature:5" }), 1))).toEqual([1]);
    expect(ids(filterTasks(tasks, f({ place: "tray:8" }), 1))).toEqual([3]);
    expect(ids(filterTasks(tasks, f({ place: "planting:3" }), 1))).toEqual([4]);
  });

  it("sorts by priority (then date) or newest first", () => {
    expect(ids(filterTasks(tasks, f({ sort: "priority" }), 1))).toEqual([4, 1, 3, 2]);
    expect(ids(filterTasks(tasks, f({ sort: "newest" }), 1))).toEqual([4, 3, 2, 1]);
  });

  it("does not change the list it is given", () => {
    const before = ids(tasks);
    filterTasks(tasks, f({ sort: "newest" }), 1);
    expect(ids(tasks)).toEqual(before);
  });
});

describe("filters in the URL", () => {
  it("writes only what differs from the defaults and reads it back", () => {
    const filters = f({ q: "beans", who: "me", priority: "high", sort: "priority" });
    const params = writeFilters(filters);
    expect(params.toString()).toBe("q=beans&who=me&priority=high&sort=priority");
    expect(readFilters(params)).toEqual(filters);
    expect(writeFilters(DEFAULT_FILTERS).toString()).toBe("");
  });

  it("keeps other query parameters and drops filters that return to default", () => {
    const next = writeFilters(f({ who: "all" }), new URLSearchParams("keep=1&who=me"));
    expect(next.toString()).toBe("keep=1");
  });

  it("falls back to defaults for junk", () => {
    const read = readFilters(new URLSearchParams("status=banana&sort=random&priority=urgent"));
    expect(read).toEqual(DEFAULT_FILTERS);
  });

  it("says whether anything but the sort order is filtered", () => {
    expect(isFiltered(DEFAULT_FILTERS)).toBe(false);
    expect(isFiltered(f({ sort: "newest" }))).toBe(false);
    expect(isFiltered(f({ q: "x" }))).toBe(true);
  });
});

describe("rescheduleDates", () => {
  it("gives tomorrow and a week on, across a month end", () => {
    expect(rescheduleDates(new Date(2026, 9, 30))).toEqual({ tomorrow: "2026-10-31", nextWeek: "2026-11-06" });
  });
});
