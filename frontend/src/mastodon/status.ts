import type { components } from "../api/schema";

export type MastodonPost = components["schemas"]["MastodonPost"];
export type MastodonSettings = components["schemas"]["MastodonSettings"];

const KINDS: Record<string, string> = { task: "Finished job", photos: "Photos", digest: "Daily digest", test: "Test post" };
export const kindLabel = (kind?: string) => KINDS[kind ?? ""] ?? kind ?? "";

const plural = (n: number, one: string) => `${n} ${one}${n === 1 ? "" : "s"}`;

/** One short line saying where a post is in its life. `now` is injectable for tests. */
export function postStatus(post: MastodonPost, now = Date.now()): { label: string; tone: "ok" | "wait" | "bad" } {
  switch (post.status) {
    case "sent":
      return { label: "Posted", tone: "ok" };
    case "failed":
      return { label: "Failed", tone: "bad" };
    case "skipped":
      return { label: "Not sent", tone: "wait" };
    case "sending":
      return { label: "Sending…", tone: "wait" };
    default: {
      const wait = Math.round((new Date(post.send_after ?? now).getTime() - now) / 60000);
      if (post.attempts) return { label: `Retrying${wait > 0 ? ` in ${plural(wait, "minute")}` : ""} (attempt ${post.attempts + 1})`, tone: "wait" };
      return { label: wait > 0 ? `Queued: sends in ${plural(wait, "minute")}` : "Queued", tone: "wait" };
    }
  }
}

/** A retry only makes sense for failed posts. */
export const canRetry = (post: MastodonPost) => post.status === "failed";

export const shouldPoll = (posts: MastodonPost[] | undefined) =>
  !!posts?.some((p) => p.status === "pending" || p.status === "sending");
