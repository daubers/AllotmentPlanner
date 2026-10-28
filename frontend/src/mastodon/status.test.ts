import { describe, expect, it } from "vitest";
import { canRetry, kindLabel, postStatus, shouldPoll, type MastodonPost } from "./status";

const NOW = Date.parse("2026-10-28T12:00:00Z");
const post = (extra: Partial<MastodonPost>): MastodonPost =>
  ({ id: 1, kind: "task", status: "pending", attempts: 0, send_after: "2026-10-28T12:00:00Z", ...extra }) as MastodonPost;

describe("postStatus", () => {
  it("reports sent and failed", () => {
    expect(postStatus(post({ status: "sent" }), NOW)).toEqual({ label: "Posted", tone: "ok" });
    expect(postStatus(post({ status: "failed" }), NOW).tone).toBe("bad");
  });
  it("says how long a batched photo post will wait", () => {
    expect(postStatus(post({ send_after: "2026-10-28T12:03:00Z" }), NOW).label).toBe("Queued: sends in 3 minutes");
    expect(postStatus(post({ send_after: "2026-10-28T12:01:00Z" }), NOW).label).toBe("Queued: sends in 1 minute");
  });
  it("is just 'Queued' once due", () => expect(postStatus(post({}), NOW).label).toBe("Queued"));
  it("shows retries with the next attempt number", () => {
    const retry = postStatus(post({ attempts: 2, send_after: "2026-10-28T12:08:00Z" }), NOW);
    expect(retry).toEqual({ label: "Retrying in 8 minutes (attempt 3)", tone: "wait" });
  });
  it("labels skipped and in-flight posts", () => {
    expect(postStatus(post({ status: "skipped" }), NOW).label).toBe("Not sent");
    expect(postStatus(post({ status: "sending" }), NOW).label).toBe("Sending…");
  });
});

describe("helpers", () => {
  it("only failed posts can be retried", () => {
    expect(canRetry(post({ status: "failed" }))).toBe(true);
    expect(canRetry(post({ status: "pending" }))).toBe(false);
  });
  it("polls while anything is in flight", () => {
    expect(shouldPoll([post({ status: "sent" })])).toBe(false);
    expect(shouldPoll([post({ status: "sent" }), post({ status: "pending" })])).toBe(true);
    expect(shouldPoll(undefined)).toBe(false);
  });
  it("names post kinds", () => {
    expect(kindLabel("digest")).toBe("Daily digest");
    expect(kindLabel("mystery")).toBe("mystery");
  });
});
