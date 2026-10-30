/** One step the person can take back. `undo` and `redo` put the map and the server back. */
export type Step = { label: string; undo(): Promise<void>; redo(): Promise<void> };

const LIMIT = 100;

/** An undo/redo stack. Steps are run one at a time so quick presses can't interleave saves. */
export class History {
  private done: Step[] = [];
  private undone: Step[] = [];
  private busy = false;
  private listeners = new Set<() => void>();

  record(step: Step): void {
    this.done.push(step);
    if (this.done.length > LIMIT) this.done.shift();
    this.undone = [];
    this.changed();
  }

  get undoLabel(): string | null {
    return this.done.at(-1)?.label ?? null;
  }

  get redoLabel(): string | null {
    return this.undone.at(-1)?.label ?? null;
  }

  async undo(): Promise<boolean> {
    return this.run(this.done, this.undone, "undo");
  }

  async redo(): Promise<boolean> {
    return this.run(this.undone, this.done, "redo");
  }

  clear(): void {
    this.done = [];
    this.undone = [];
    this.changed();
  }

  subscribe(fn: () => void): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  private async run(from: Step[], to: Step[], way: "undo" | "redo"): Promise<boolean> {
    if (this.busy) return false;
    const step = from.at(-1);
    if (!step) return false;
    this.busy = true;
    try {
      await step[way]();
      from.pop();
      to.push(step);
      return true;
    } catch {
      return false; // the step stays where it was, so it can be tried again
    } finally {
      this.busy = false;
      this.changed();
    }
  }

  private changed(): void {
    this.listeners.forEach((fn) => fn());
  }
}
