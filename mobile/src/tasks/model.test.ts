import { completeRequest, createRequest, daysFrom, dueLabel, groupTasks, localDate, localJob, reopenRequest, withStatus, type Task } from "./model";

const t = (id: number, extra: Partial<Task> = {}): Task => ({ id, title: `t${id}`, status: "todo", ...extra }) as Task;

test("dates are local calendar days", () => {
  expect(localDate(new Date(2026, 10, 2, 23, 30))).toBe("2026-11-02");
  expect(daysFrom(1, new Date(2026, 9, 31))).toBe("2026-11-01");
  expect(daysFrom(7, new Date(2026, 11, 28))).toBe("2027-01-04");
});

test("open jobs are bucketed by due date and done ones are left out", () => {
  const g = groupTasks(
    [t(1, { due_date: "2026-11-01" }), t(2, { due_date: "2026-11-02" }), t(3, { due_date: "2026-11-09" }), t(4), t(5, { status: "done", due_date: "2026-11-02" }), t(6, { status: "doing", due_date: "2026-11-02" })],
    "2026-11-02",
  );
  expect(g.overdue.map((x) => x.id)).toEqual([1]);
  expect(g.today.map((x) => x.id)).toEqual([2, 6]);
  expect(g.upcoming.map((x) => x.id)).toEqual([3]);
  expect(g.undated.map((x) => x.id)).toEqual([4]);
});

test("due dates read plainly", () => {
  const today = "2026-11-02";
  expect(dueLabel("2026-11-02", today)).toBe("Due today");
  expect(dueLabel("2026-11-03", today)).toBe("Tomorrow");
  expect(dueLabel("2026-11-01", today)).toBe("1 day late");
  expect(dueLabel("2026-10-30", today)).toBe("3 days late");
  expect(dueLabel("2026-11-12", today)).toBe("Due 12 Nov");
  expect(dueLabel(null, today)).toBe("");
});

test("a new job is queued as a POST, pinned to a bed or a point", () => {
  expect(createRequest(1, { title: "  Water the beans ", due_date: "2026-11-02", priority: "high", feature_id: 5 })).toEqual({
    method: "POST",
    path: "/api/v1/allotments/1/tasks",
    body: { title: "Water the beans", priority: "high", due_date: "2026-11-02", feature_id: 5 },
  });
  const here = createRequest(1, { title: "Dig", location: { lat: 51.5, lng: -1.25 } });
  expect(here.body).toEqual({ title: "Dig", priority: "normal", location: { type: "Point", coordinates: [-1.25, 51.5] } });
  // a bed wins over a point: the server pins a job to one place
  expect(createRequest(1, { title: "x", feature_id: 2, location: { lat: 1, lng: 2 } }).body).not.toHaveProperty("location");
});

test("ticking and unticking are queued requests", () => {
  expect(completeRequest(1, 9)).toEqual({ method: "POST", path: "/api/v1/allotments/1/tasks/9/complete" });
  expect(reopenRequest(1, 9)).toEqual({ method: "POST", path: "/api/v1/allotments/1/tasks/9/reopen" });
});

test("a job made offline shows at once with a temporary negative id", () => {
  const job = localJob({ title: " Prune ", due_date: "2026-11-02" }, 1234);
  expect(job).toMatchObject({ id: -1234, title: "Prune", status: "todo", priority: "normal", due_date: "2026-11-02" });
});

test("a tick shows before the server confirms, without touching the other jobs", () => {
  const list = [t(1), t(2)];
  const ticked = withStatus(list, 2, "done");
  expect(ticked.map((x) => x.status)).toEqual(["todo", "done"]);
  expect(list[1].status).toBe("todo");
  expect(withStatus(ticked, 2, "todo")[1].status).toBe("todo");
});
