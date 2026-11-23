import { describe, expect, it } from "vitest";
import type { components } from "../api/schema";
import { addTool, bringSummary, extrasOf, previewBring, removeTool } from "./bring";

type Task = components["schemas"]["Task"];
const tool = (id: number, name: string, status: "in_service" | "out_of_action" = "in_service") => ({ id, name, kind: null, kind_label: "Other", quantity: 1, status });
const task = (id: number, equipment: ReturnType<typeof tool>[], status: Task["status"] = "todo"): Task => ({ id, title: `Task ${id}`, status, equipment }) as Task;
const none = { adds: [], removes: [] };
const names = (id: number) => ({ 5: { name: "Wheelbarrow", outOfAction: false }, 6: { name: "Old hoe", outOfAction: true } })[id as 5 | 6];
const row = (r: { id: number; source: string }) => [r.id, r.source];

describe("previewBring", () => {
  it("lists the equipment on the picked tasks, once, by name", () => {
    const rows = previewBring([task(1, [tool(2, "Fork"), tool(1, "Border spade")]), task(2, [tool(2, "Fork")])], undefined, none, names);
    expect(rows.map((r) => r.name)).toEqual(["Border spade", "Fork"]);
    expect(rows.every((r) => r.source === "task")).toBe(true);
  });

  it("ignores finished tasks", () => {
    expect(previewBring([task(1, [tool(1, "Spade")], "done")], undefined, none, names)).toEqual([]);
  });

  it("keeps the server's suggestions only for tasks still picked", () => {
    const server = [{ ...tool(3, "Dibber"), source: "suggested" as const, task_ids: [7] }];
    expect(previewBring([task(7, [])], server, none, names).map(row)).toEqual([[3, "suggested"]]);
    expect(previewBring([task(8, [])], server, none, names)).toEqual([]); // that task was unpicked
  });

  it("puts what a task needs ahead of suggestions and extras", () => {
    const server = [{ ...tool(3, "Dibber"), source: "suggested" as const, task_ids: [7] }];
    const rows = previewBring([task(1, [tool(1, "Spade")]), task(7, [])], server, { adds: [5], removes: [] }, names);
    expect(rows.map(row)).toEqual([[1, "task"], [3, "suggested"], [5, "extra"]]);
    expect(rows[2].name).toBe("Wheelbarrow");
  });

  it("hides what was removed, whatever brought it, and marks what is out of action", () => {
    const picked = [task(1, [tool(1, "Spade"), tool(2, "Fork", "out_of_action")])];
    const rows = previewBring(picked, undefined, { adds: [6], removes: [1] }, names);
    expect(rows.map((r) => r.id)).toEqual([2, 6]);
    expect(rows.map((r) => r.outOfAction)).toEqual([true, true]);
  });

  it("skips an extra it does not know", () => {
    expect(previewBring([], undefined, { adds: [99], removes: [] }, names)).toEqual([]);
  });
});

describe("changing the list", () => {
  it("removing a hand-added tool un-adds it; removing a task's tool hides it", () => {
    expect(removeTool({ adds: [5], removes: [] }, 5)).toEqual({ adds: [], removes: [] });
    expect(removeTool(none, 1)).toEqual({ adds: [], removes: [1] });
    expect(removeTool({ adds: [], removes: [1] }, 1)).toEqual({ adds: [], removes: [1] });
  });

  it("adding something hidden shows it again; something new is added by hand", () => {
    expect(addTool({ adds: [], removes: [1] }, 1, false)).toEqual({ adds: [1], removes: [] });
    expect(addTool({ adds: [], removes: [1] }, 1, true)).toEqual({ adds: [], removes: [] }); // a task brings it anyway
    expect(addTool(none, 5, false)).toEqual({ adds: [5], removes: [] });
    expect(addTool({ adds: [5], removes: [] }, 5, false)).toEqual({ adds: [5], removes: [] });
  });

  it("reads a visit's saved extras", () => {
    expect(extrasOf({ equipment_extras: [{ equipment_id: 5, mode: "add" }, { equipment_id: 1, mode: "remove" }] })).toEqual({ adds: [5], removes: [1] });
    expect(extrasOf(undefined)).toEqual(none);
  });
});

describe("bringSummary", () => {
  it("names a few and counts the rest", () => {
    expect(bringSummary([])).toBe("");
    expect(bringSummary(undefined)).toBe("");
    expect(bringSummary([{ name: "Spade" }, { name: "Fork" }])).toBe("Spade, Fork");
    expect(bringSummary([{ name: "A" }, { name: "B" }, { name: "C" }, { name: "D" }, { name: "E" }])).toBe("A, B, C +2");
  });
});
