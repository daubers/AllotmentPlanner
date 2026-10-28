/** A durable to-do list of things to send to the server, worked through whenever there is signal.
 *
 * Everything the app writes goes through here, so the field is never blocked by a bad connection:
 * a job is saved first and sent later, retrying with growing delays. A job that the server
 * rejects outright (bad input, no permission) is parked as failed with the reason, for the person
 * to retry or drop, rather than retried forever. */

export type JobStatus = "pending" | "failed";

export type Job = {
  id: string;
  kind: string;
  payload: unknown;
  status: JobStatus;
  attempts: number;
  /** Earliest time (ms since epoch) to try again. */
  nextAt: number;
  error: string | null;
  createdAt: number;
};

export interface JobStore {
  /** Adds the job unless one with that id exists. Returns whether it was added. */
  add(job: Job): Promise<boolean>;
  get(id: string): Promise<Job | null>;
  /** Pending jobs due at ``now``, oldest first. */
  due(now: number): Promise<Job[]>;
  update(id: string, patch: Partial<Pick<Job, "status" | "attempts" | "nextAt" | "error">>): Promise<void>;
  remove(id: string): Promise<void>;
  list(): Promise<Job[]>;
}

/** The job can never succeed as it stands: stop retrying and show why. */
export class PermanentError extends Error {}
/** Worth trying again later (no signal, server busy). */
export class RetryableError extends Error {}

export type JobContext = { onProgress: (fraction: number) => void };
export type Handler = (payload: any, ctx: JobContext) => Promise<void>;

export type QueueState = {
  pending: number;
  failed: number;
  /** The job being sent now and how far through it is (0 to 1). */
  active: { id: string; kind: string; progress: number } | null;
};

const DELAYS_S = [5, 30, 120, 600, 1800, 3600];

export function backoffMs(attempts: number): number {
  return DELAYS_S[Math.min(Math.max(attempts, 1), DELAYS_S.length) - 1] * 1000;
}

export class JobQueue {
  private running = false;
  private listeners = new Set<() => void>();
  private active: QueueState["active"] = null;
  private counts = { pending: 0, failed: 0 };

  constructor(
    private readonly store: JobStore,
    private readonly handlers: Record<string, Handler>,
    private readonly now: () => number = Date.now,
  ) {}

  subscribe(fn: () => void): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  state(): QueueState {
    return { ...this.counts, active: this.active };
  }

  /** Save a job. A repeat of an id that is already queued is ignored, so a double tap can't send twice. */
  async enqueue(kind: string, payload: unknown, id: string = newId()): Promise<string> {
    await this.store.add({
      id,
      kind,
      payload,
      status: "pending",
      attempts: 0,
      nextAt: 0,
      error: null,
      createdAt: this.now(),
    });
    await this.refreshCounts();
    return id;
  }

  async retry(id: string): Promise<void> {
    await this.store.update(id, { status: "pending", nextAt: 0, error: null });
    await this.refreshCounts();
  }

  async drop(id: string): Promise<void> {
    await this.store.remove(id);
    await this.refreshCounts();
  }

  async jobs(): Promise<Job[]> {
    return this.store.list();
  }

  /** Try every job that is due, once. Safe to call often; overlapping calls do nothing. */
  async run(): Promise<void> {
    if (this.running) return;
    this.running = true;
    try {
      await this.refreshCounts();
      for (const job of await this.store.due(this.now())) {
        await this.attempt(job);
      }
    } finally {
      this.active = null;
      this.running = false;
      await this.refreshCounts();
    }
  }

  private async attempt(job: Job): Promise<void> {
    const handler = this.handlers[job.kind];
    if (!handler) {
      await this.store.update(job.id, { status: "failed", error: `Unknown job type "${job.kind}"` });
      return;
    }
    this.active = { id: job.id, kind: job.kind, progress: 0 };
    this.emit();
    try {
      await handler(job.payload, {
        onProgress: (fraction) => {
          if (this.active) {
            this.active = { ...this.active, progress: fraction };
            this.emit();
          }
        },
      });
      await this.store.remove(job.id);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      if (err instanceof PermanentError) {
        await this.store.update(job.id, { status: "failed", error: message });
      } else {
        const attempts = job.attempts + 1;
        await this.store.update(job.id, {
          attempts,
          nextAt: this.now() + backoffMs(attempts),
          error: message,
        });
      }
    }
  }

  private async refreshCounts(): Promise<void> {
    const all = await this.store.list();
    this.counts = {
      pending: all.filter((j) => j.status === "pending").length,
      failed: all.filter((j) => j.status === "failed").length,
    };
    this.emit();
  }

  private emit(): void {
    this.listeners.forEach((fn) => fn());
  }
}

export function newId(): string {
  const bytes = Array.from({ length: 16 }, () => Math.floor(Math.random() * 256));
  return bytes.map((b) => b.toString(16).padStart(2, "0")).join("");
}

/** An in-memory store, for tests. */
export class MemoryJobStore implements JobStore {
  private jobs = new Map<string, Job>();
  async add(job: Job) {
    if (this.jobs.has(job.id)) return false;
    this.jobs.set(job.id, { ...job });
    return true;
  }
  async get(id: string) {
    return this.jobs.get(id) ?? null;
  }
  async due(now: number) {
    return [...this.jobs.values()]
      .filter((j) => j.status === "pending" && j.nextAt <= now)
      .sort((a, b) => a.createdAt - b.createdAt || a.id.localeCompare(b.id));
  }
  async update(id: string, patch: Parameters<JobStore["update"]>[1]) {
    const job = this.jobs.get(id);
    if (job) Object.assign(job, patch);
  }
  async remove(id: string) {
    this.jobs.delete(id);
  }
  async list() {
    return [...this.jobs.values()].sort((a, b) => a.createdAt - b.createdAt);
  }
}
