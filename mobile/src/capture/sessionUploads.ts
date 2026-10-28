import type { Job } from "../queue/queue";

export type UploadProgress = { total: number; waiting: number; failed: number };

/** How many of a capture session's photos are still waiting to reach the server. */
export function sessionUploads(jobs: Job[], sessionId: string): UploadProgress {
  const mine = jobs.filter(
    (j) => j.kind === "upload" && (j.payload as { fields?: Record<string, string> }).fields?.capture_session === sessionId,
  );
  return {
    total: mine.length,
    waiting: mine.filter((j) => j.status === "pending").length,
    failed: mine.filter((j) => j.status === "failed").length,
  };
}
