import { describe, expect, it } from "vitest";
import { groupTasks, localDate, type Task } from "./group";

const t = (id: number, extra: Partial<Task>): Task => ({ id, title: `t${id}`, status: "todo", ...extra }) as Task;

describe("groupTasks", () => {
  it("buckets tasks by status and due date relative to today", () => {
    const g = groupTasks(
      [
        t(1, { due_date: "2026-11-01" }),
        t(2, { due_date: "2026-11-02" }),
        t(3, { due_date: "2026-11-03" }),
        t(4, { due_date: null }),
        t(5, { status: "done", due_date: "2026-10-01" }),
        t(6, { status: "doing", due_date: "2026-11-02" }),
      ],
      "2026-11-02",
    );
    expect(g.overdue.map((x) => x.id)).toEqual([1]);
    expect(g.today.map((x) => x.id)).toEqual([2, 6]);
    expect(g.upcoming.map((x) => x.id)).toEqual([3]);
    expect(g.undated.map((x) => x.id)).toEqual([4]);
    expect(g.done.map((x) => x.id)).toEqual([5]);
  });

  it("lists the most recently completed first", () => {
    const g = groupTasks([
      t(1, { status: "done", completed_at: "2026-11-01T10:00:00Z" }),
      t(2, { status: "done", completed_at: "2026-11-02T10:00:00Z" }),
    ]);
    expect(g.done.map((x) => x.id)).toEqual([2, 1]);
  });

  it("formats local dates with zero padding", () => {
    expect(localDate(new Date(2026, 0, 5))).toBe("2026-01-05");
  });
});
