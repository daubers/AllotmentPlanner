import { sessionUploads } from "./sessionUploads";
import type { Job } from "../queue/queue";

const job = (id: string, session: string, status: Job["status"], kind = "upload"): Job => ({
  id,
  kind,
  status,
  payload: { fields: { capture_session: session } },
  attempts: 0,
  nextAt: 0,
  error: null,
  createdAt: 0,
});

test("only this session's waiting uploads are counted", () => {
  const jobs = [job("1", "a", "pending"), job("2", "a", "pending"), job("3", "a", "failed"), job("4", "b", "pending"), job("5", "a", "pending", "request")];
  expect(sessionUploads(jobs, "a")).toEqual({ total: 3, waiting: 2, failed: 1 });
  expect(sessionUploads(jobs, "none")).toEqual({ total: 0, waiting: 0, failed: 0 });
});
