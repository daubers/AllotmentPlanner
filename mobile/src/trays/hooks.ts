import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { useApp } from "../state/AppProvider";
import { applyLocally, cellsRequest, countsOf, type Cell, type CellChange } from "./model";

export function useTrays() {
  const { api, allotmentId, session } = useApp();
  return useQuery({
    queryKey: ["trays", session.serverUrl, allotmentId],
    enabled: allotmentId !== null,
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/allotments/{allotment_id}/trays", {
        params: { path: { allotment_id: allotmentId as number } },
      });
      if (error || !data) throw new Error("Couldn't load your trays");
      return data;
    },
  });
}

export function useTray(id: number) {
  const { api, allotmentId, session } = useApp();
  return useQuery({
    queryKey: ["tray", session.serverUrl, allotmentId, id],
    enabled: allotmentId !== null,
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/allotments/{allotment_id}/trays/{tray_id}", {
        params: { path: { allotment_id: allotmentId as number, tray_id: id } },
      });
      if (error || !data) throw new Error("Couldn't load that tray");
      return data;
    },
  });
}

/** Change the chosen cells: shown at once, and sent when there is signal (so it works in the greenhouse). */
export function useCellChange(trayId: number) {
  const { queue, allotmentId, session } = useApp();
  const client = useQueryClient();
  return useCallback(
    async (selected: ReadonlySet<string>, set: CellChange) => {
      if (allotmentId === null || selected.size === 0) return;
      const key = ["tray", session.serverUrl, allotmentId, trayId];
      client.setQueryData(key, (old: any) => {
        if (!old) return old;
        const cells = applyLocally((old.cells ?? []) as Cell[], selected, set);
        return { ...old, cells, counts: countsOf(old.rows, old.cols, cells) };
      });
      await queue.enqueue("request", cellsRequest(trayId, allotmentId, selected, set));
      void queue.run();
    },
    [queue, allotmentId, session.serverUrl, trayId, client],
  );
}
