import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef } from "react";
import { useApp, useQueueState } from "../state/AppProvider";
import type { Checklist, Item } from "./model";

export function useChecklist() {
  const { api, allotmentId, session } = useApp();
  const { pending } = useQueueState();
  const query = useQuery({
    queryKey: ["measurements", session.serverUrl, allotmentId],
    enabled: allotmentId !== null,
    queryFn: async (): Promise<Checklist> => {
      const { data, error } = await api.GET("/api/v1/allotments/{allotment_id}/measurements", {
        params: { path: { allotment_id: allotmentId as number } },
      });
      if (error || !data) throw new Error("Couldn't load the checklist");
      return data as unknown as Checklist;
    },
  });
  // After offline changes have all been sent, take the server's version.
  const wasPending = useRef(false);
  useEffect(() => {
    if (wasPending.current && pending === 0) void query.refetch();
    wasPending.current = pending > 0;
  }, [pending]); // eslint-disable-line react-hooks/exhaustive-deps
  return query;
}

/** Corner positions of every drawn shape, by feature id. */
export function useShapes() {
  const { api, allotmentId, session } = useApp();
  return useQuery({
    queryKey: ["shapes", session.serverUrl, allotmentId],
    enabled: allotmentId !== null,
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/allotments/{allotment_id}/features", {
        params: { path: { allotment_id: allotmentId as number } },
      });
      if (error || !data) throw new Error("Couldn't load the map shapes");
      const out = new Map<number, { type: string; coordinates: any }>();
      for (const f of (data as any).features ?? []) out.set(f.id, f.geometry);
      return out;
    },
  });
}

/** Save a measurement at once on screen and send it when there is signal. */
export function useRecord() {
  const { queue, allotmentId, session } = useApp();
  const client = useQueryClient();
  return useCallback(
    async (item: Item, patch: { value_m?: number | null; note?: string; skipped?: boolean }) => {
      const key = ["measurements", session.serverUrl, allotmentId];
      client.setQueryData<Checklist>(key, (old) => {
        if (!old) return old;
        const items = old.items.map((i) => (i.id === item.id ? { ...i, ...patch } : i));
        const live = items.filter((i) => !i.stale && !i.skipped);
        return {
          ...old,
          items,
          total: live.length,
          measured: live.filter((i) => i.value_m !== null).length,
          features: old.features.map((f) => {
            const mine = live.filter((i) => i.feature_id === f.id);
            return { ...f, total: mine.length, measured: mine.filter((i) => i.value_m !== null).length };
          }),
        };
      });
      await queue.enqueue("request", {
        method: "PATCH",
        path: `/api/v1/allotments/${allotmentId}/measurements/${item.id}`,
        body: patch,
      });
      void queue.run();
    },
    [queue, allotmentId, client, session.serverUrl],
  );
}
