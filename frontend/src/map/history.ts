/** One step the person can take back. `undo` and `redo` put the map and the server back. */
export type Step = {
  label: string;
  undo(): Promise<void>;
  redo(): Promise<void>;
  /** The feature this step changed (read late, as undoing a delete gives it a new id). */
  target?: () => number;
};

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

  /** Label of the latest undoable step for one feature. */
  undoLabelFor(id: number): string | null {
    return this.latest(this.done, id)?.label ?? null;
  }

  redoLabelFor(id: number): string | null {
    return this.latest(this.undone, id)?.label ?? null;
  }

  /** Undoes the latest step, or with an id, the latest step for that feature alone. */
  async undo(id?: number): Promise<boolean> {
    return this.run(this.done, this.undone, "undo", id);
  }

  async redo(id?: number): Promise<boolean> {
    return this.run(this.undone, this.done, "redo", id);
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

  private latest(steps: Step[], id?: number): Step | undefined {
    if (id === undefined) return steps.at(-1);
    for (let i = steps.length - 1; i >= 0; i--) if (steps[i].target?.() === id) return steps[i];
    return undefined;
  }

  private async run(from: Step[], to: Step[], way: "undo" | "redo", id?: number): Promise<boolean> {
    if (this.busy) return false;
    const step = this.latest(from, id);
    if (!step) return false;
    this.busy = true;
    try {
      await step[way]();
      from.splice(from.lastIndexOf(step), 1);
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
