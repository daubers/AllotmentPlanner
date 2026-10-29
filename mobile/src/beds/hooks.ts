import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { useApp } from "../state/AppProvider";
import { ringOf, statusRequest, type LonLat } from "./geometry";

export type Bed = { id: number; name: string; ring: LonLat[] };

/** Beds: map shapes drawn as areas and called "bed". */
export function useBeds() {
  const { api, allotmentId, session } = useApp();
  return useQuery({
    queryKey: ["beds", session.serverUrl, allotmentId],
    enabled: allotmentId !== null,
    queryFn: async (): Promise<Bed[]> => {
      const { data, error } = await api.GET("/api/v1/allotments/{allotment_id}/features", {
        params: { path: { allotment_id: allotmentId as number } },
      });
      if (error || !data) throw new Error("Couldn't load your beds");
      return ((data as any).features ?? [])
        .filter((f: any) => f.properties?.kind === "bed" && f.geometry?.type === "Polygon")
        .map((f: any) => ({ id: f.id as number, name: (f.properties.name as string) || `Bed ${f.id}`, ring: ringOf(f.geometry) }));
    },
  });
}

export function usePlantings() {
  const { api, allotmentId, session } = useApp();
  return useQuery({
    queryKey: ["plantings", session.serverUrl, allotmentId],
    enabled: allotmentId !== null,
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/allotments/{allotment_id}/plantings", {
        params: { path: { allotment_id: allotmentId as number } },
      });
      if (error || !data) throw new Error("Couldn't load what is growing");
      return data;
    },
  });
}

/** Change a planting's state: shown at once, sent when there is signal. */
export function usePlantingStatus() {
  const { queue, allotmentId, session } = useApp();
  const client = useQueryClient();
  return useCallback(
    async (plantingId: number, status: string) => {
      if (allotmentId === null) return;
      client.setQueryData(["plantings", session.serverUrl, allotmentId], (old: any) =>
        Array.isArray(old) ? old.map((p) => (p.id === plantingId ? { ...p, status } : p)) : old,
      );
      await queue.enqueue("request", statusRequest(allotmentId, plantingId, status));
      void queue.run();
    },
    [queue, allotmentId, session.serverUrl, client],
  );
}
