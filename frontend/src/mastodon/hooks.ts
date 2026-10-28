import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components } from "../api/schema";
import { shouldPoll, type MastodonPost, type MastodonSettings } from "./status";

export type SettingsInput = components["schemas"]["MastodonSettingsIn"];

const path = (allotmentId: number) => ({ path: { allotment_id: allotmentId } });
const message = (error: unknown, fallback: string) => (error as { message?: string } | undefined)?.message ?? fallback;

export function useMastodon(allotmentId: number) {
  return useQuery({
    queryKey: ["mastodon", allotmentId],
    queryFn: async (): Promise<MastodonSettings | undefined> =>
      (await api.GET("/api/v1/allotments/{allotment_id}/mastodon", { params: path(allotmentId) })).data,
  });
}

/** Recent posts; refreshes every few seconds while something is queued or sending. */
export function useMastodonPosts(allotmentId: number) {
  return useQuery({
    queryKey: ["mastodon-posts", allotmentId],
    queryFn: async (): Promise<MastodonPost[]> =>
      (await api.GET("/api/v1/allotments/{allotment_id}/mastodon/posts", { params: { ...path(allotmentId), query: { limit: 30 } } })).data ?? [],
    refetchInterval: (q) => (shouldPoll(q.state.data) ? 3000 : false),
  });
}

export function useMastodonActions(allotmentId: number) {
  const qc = useQueryClient();
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["mastodon", allotmentId] });
    void qc.invalidateQueries({ queryKey: ["mastodon-posts", allotmentId] });
  };
  return {
    save: useMutation({
      mutationFn: async (body: SettingsInput) => {
        const { data, error } = await api.PUT("/api/v1/allotments/{allotment_id}/mastodon", { params: path(allotmentId), body });
        if (!data) throw new Error(message(error, "Could not save"));
        return data;
      },
      onSuccess: refresh,
    }),
    disconnect: useMutation({
      mutationFn: async () => {
        const { error, response } = await api.DELETE("/api/v1/allotments/{allotment_id}/mastodon", { params: path(allotmentId) });
        if (!response.ok) throw new Error(message(error, "Could not disconnect"));
      },
      onSuccess: refresh,
    }),
    test: useMutation({
      mutationFn: async () => {
        const { data, error } = await api.POST("/api/v1/allotments/{allotment_id}/mastodon/test", { params: path(allotmentId) });
        if (!data) throw new Error(message(error, "Could not queue the test post"));
        return data;
      },
      onSuccess: refresh,
    }),
    retry: useMutation({
      mutationFn: async (postId: number) => {
        const { data, error } = await api.POST("/api/v1/allotments/{allotment_id}/mastodon/posts/{post_id}/retry", {
          params: { path: { allotment_id: allotmentId, post_id: postId } },
        });
        if (!data) throw new Error(message(error, "Could not retry"));
        return data;
      },
      onSuccess: refresh,
    }),
  };
}
