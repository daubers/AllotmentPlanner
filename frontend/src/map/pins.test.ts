import L from "leaflet";
import { describe, expect, it } from "vitest";
import type { Task } from "../tasks/group";
import { pinGroups, pinPopup, taskLatLng } from "./pins";

const task = (id: number, extra: Partial<Task>): Task => ({ id, title: `t${id}`, status: "todo", ...extra }) as Task;
const bed = L.polygon([[51, -1], [51.002, -1], [51.002, -0.998], [51, -0.998]]);
const find = (id: number) => (id === 1 ? bed : undefined);

describe("task pins", () => {
  it("prefers the task's own point over its feature", () => {
    const p = taskLatLng(task(1, { feature_id: 1, location: { type: "Point", coordinates: [-0.5, 50.5] } }), find)!;
    expect([p.lat, p.lng]).toEqual([50.5, -0.5]);
  });

  it("uses the centre of the pinned feature, and nothing for unpinned or unknown features", () => {
    const p = taskLatLng(task(1, { feature_id: 1 }), find)!;
    expect(p.lat).toBeCloseTo(51.001);
    expect(p.lng).toBeCloseTo(-0.999);
    expect(taskLatLng(task(2, {}), find)).toBeNull();
    expect(taskLatLng(task(3, { feature_id: 99 }), find)).toBeNull();
  });

  it("uses the position of a marker or circle feature", () => {
    const tree = L.circle([51.5, -1.5], { radius: 2 });
    expect(taskLatLng(task(1, { feature_id: 5 }), () => tree)!.lat).toBe(51.5);
  });

  it("groups tasks sharing a position and skips done and unpinned tasks", () => {
    const groups = pinGroups(
      [task(1, { feature_id: 1 }), task(2, { feature_id: 1 }), task(3, { feature_id: 1, status: "done" }), task(4, {})],
      find,
    );
    expect(groups).toHaveLength(1);
    expect(groups[0].tasks.map((t) => t.id)).toEqual([1, 2]);
  });

  it("renders titles as text, not HTML", () => {
    const el = pinPopup([task(1, { title: "<img src=x onerror=alert(1)>", due_date: "2026-11-01" })]);
    expect(el.querySelector("img")).toBeNull();
    expect(el.textContent).toContain("<img src=x onerror=alert(1)> (2026-11-01)");
  });
});
