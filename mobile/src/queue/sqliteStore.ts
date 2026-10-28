import * as SQLite from "expo-sqlite";
import type { Job, JobStore } from "./queue";

type Row = {
  id: string;
  kind: string;
  payload: string;
  status: Job["status"];
  attempts: number;
  next_at: number;
  error: string | null;
  created_at: number;
};

const toJob = (r: Row): Job => ({
  id: r.id,
  kind: r.kind,
  payload: JSON.parse(r.payload),
  status: r.status,
  attempts: r.attempts,
  nextAt: r.next_at,
  error: r.error,
  createdAt: r.created_at,
});

/** The queue on disk, so waiting uploads survive the app being closed or the phone restarting. */
export class SqliteJobStore implements JobStore {
  private constructor(private readonly db: SQLite.SQLiteDatabase) {}

  static async open(name = "queue.db"): Promise<SqliteJobStore> {
    const db = await SQLite.openDatabaseAsync(name);
    await db.execAsync(`
      PRAGMA journal_mode = WAL;
      CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY NOT NULL,
        kind TEXT NOT NULL,
        payload TEXT NOT NULL,
        status TEXT NOT NULL,
        attempts INTEGER NOT NULL DEFAULT 0,
        next_at INTEGER NOT NULL DEFAULT 0,
        error TEXT,
        created_at INTEGER NOT NULL
      );
    `);
    return new SqliteJobStore(db);
  }

  async add(job: Job): Promise<boolean> {
    const res = await this.db.runAsync(
      "INSERT OR IGNORE INTO jobs (id, kind, payload, status, attempts, next_at, error, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
      [job.id, job.kind, JSON.stringify(job.payload), job.status, job.attempts, job.nextAt, job.error, job.createdAt],
    );
    return res.changes > 0;
  }

  async get(id: string): Promise<Job | null> {
    const row = await this.db.getFirstAsync<Row>("SELECT * FROM jobs WHERE id = ?", [id]);
    return row ? toJob(row) : null;
  }

  async due(now: number): Promise<Job[]> {
    const rows = await this.db.getAllAsync<Row>(
      "SELECT * FROM jobs WHERE status = 'pending' AND next_at <= ? ORDER BY created_at, id",
      [now],
    );
    return rows.map(toJob);
  }

  async update(id: string, patch: Parameters<JobStore["update"]>[1]): Promise<void> {
    const columns: Record<string, string> = { status: "status", attempts: "attempts", nextAt: "next_at", error: "error" };
    const sets = Object.keys(patch).map((k) => `${columns[k]} = ?`);
    if (!sets.length) return;
    const values = Object.values(patch) as (string | number | null)[];
    await this.db.runAsync(`UPDATE jobs SET ${sets.join(", ")} WHERE id = ?`, [...values, id]);
  }

  async remove(id: string): Promise<void> {
    await this.db.runAsync("DELETE FROM jobs WHERE id = ?", [id]);
  }

  async list(): Promise<Job[]> {
    const rows = await this.db.getAllAsync<Row>("SELECT * FROM jobs ORDER BY created_at, id");
    return rows.map(toJob);
  }
}
