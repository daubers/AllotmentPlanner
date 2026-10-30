import { describe, expect, it } from "vitest";
import { History } from "./history";

function counter() {
  const log: string[] = [];
  const step = (label: string) => ({
    label,
    undo: async () => void log.push(`undo ${label}`),
    redo: async () => void log.push(`redo ${label}`),
  });
  return { log, step };
}

describe("History", () => {
  it("undoes the latest step and can redo it", async () => {
    const h = new History();
    const { log, step } = counter();
    h.record(step("move"));
    h.record(step("rename"));
    expect(h.undoLabel).toBe("rename");
    await h.undo();
    expect(h.undoLabel).toBe("move");
    expect(h.redoLabel).toBe("rename");
    await h.redo();
    expect(log).toEqual(["undo rename", "redo rename"]);
    expect(h.redoLabel).toBeNull();
  });

  it("forgets the redo trail once something new happens", async () => {
    const h = new History();
    const { step } = counter();
    h.record(step("a"));
    await h.undo();
    h.record(step("b"));
    expect(h.redoLabel).toBeNull();
  });

  it("keeps a step that failed so it can be tried again", async () => {
    const h = new History();
    h.record({ label: "x", undo: async () => Promise.reject(new Error("offline")), redo: async () => {} });
    expect(await h.undo()).toBe(false);
    expect(h.undoLabel).toBe("x");
  });

  it("ignores a second undo while one is running", async () => {
    const h = new History();
    let release = () => {};
    const gate = new Promise<void>((r) => (release = r));
    h.record({ label: "slow", undo: () => gate, redo: async () => {} });
    h.record({ label: "other", undo: async () => {}, redo: async () => {} });
    const first = h.undo();
    expect(await h.undo()).toBe(false);
    release();
    await first;
    expect(h.undoLabel).toBe("slow");
  });

  it("tells listeners and caps its length", async () => {
    const h = new History();
    let n = 0;
    h.subscribe(() => n++);
    const { step } = counter();
    for (let i = 0; i < 120; i++) h.record(step(String(i)));
    let depth = 0;
    while (await h.undo()) depth++;
    expect(depth).toBe(100);
    expect(n).toBeGreaterThan(100);
  });
});
