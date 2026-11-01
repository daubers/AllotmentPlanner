import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useSyncExternalStore } from "react";
import { api } from "../api/client";
import type { components } from "../api/schema";

export type DayList = components["schemas"]["DayList"];

const path = (allotmentId: number) => ({ path: { allotment_id: allotmentId } });
const listPath = (allotmentId: number, listId: number) => ({ path: { allotment_id: allotmentId, list_id: listId } });
const failure = (error: unknown, fallback: string) => (error as { message?: string } | undefined)?.message ?? fallback;

export function useDayLists(allotmentId: number) {
  return useQuery({
    queryKey: ["day-lists", allotmentId],
    queryFn: async (): Promise<DayList[]> =>
      (await api.GET("/api/v1/allotments/{allotment_id}/day-lists", { params: path(allotmentId) })).data ?? [],
  });
}

/** The todo sheet for one list (done jobs stay on it). */
export function useDayListSheet(allotmentId: number, listId: number | null) {
  return useQuery({
    queryKey: ["day-list-sheet", allotmentId, listId],
    enabled: listId != null,
    queryFn: async () =>
      (await api.GET("/api/v1/allotments/{allotment_id}/day-lists/{list_id}/todo", { params: listPath(allotmentId, listId!) })).data,
  });
}

export function useDayListActions(allotmentId: number) {
  const qc = useQueryClient();
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["day-lists", allotmentId] });
    void qc.invalidateQueries({ queryKey: ["day-list-sheet", allotmentId] });
  };
  return {
    create: useMutation({
      mutationFn: async (body: { name: string; date?: string | null; task_ids?: number[] }): Promise<DayList> => {
        const { data, error } = await api.POST("/api/v1/allotments/{allotment_id}/day-lists", { params: path(allotmentId), body });
        if (!data) throw new Error(failure(error, "Could not make the list"));
        return data;
      },
      onSuccess: refresh,
    }),
    update: useMutation({
      mutationFn: async ({ id, body }: { id: number; body: { name?: string; date?: string | null } }) => {
        const { data, error } = await api.PATCH("/api/v1/allotments/{allotment_id}/day-lists/{list_id}", { params: listPath(allotmentId, id), body });
        if (!data) throw new Error(failure(error, "Could not save the list"));
        return data;
      },
      onSuccess: refresh,
    }),
    remove: useMutation({
      mutationFn: async (id: number) => {
        const { error } = await api.DELETE("/api/v1/allotments/{allotment_id}/day-lists/{list_id}", { params: listPath(allotmentId, id) });
        if (error) throw new Error(failure(error, "Could not delete the list"));
      },
      onSuccess: refresh,
    }),
    addTasks: useMutation({
      mutationFn: async ({ id, taskIds }: { id: number; taskIds: number[] }) => {
        const { data, error } = await api.POST("/api/v1/allotments/{allotment_id}/day-lists/{list_id}/tasks", {
          params: listPath(allotmentId, id),
          body: { task_ids: taskIds },
        });
        if (!data) throw new Error(failure(error, "Could not add those tasks"));
        return data;
      },
      onSuccess: refresh,
    }),
    removeTask: useMutation({
      mutationFn: async ({ id, taskId }: { id: number; taskId: number }) => {
        const { error } = await api.DELETE("/api/v1/allotments/{allotment_id}/day-lists/{list_id}/tasks/{task_id}", {
          params: { path: { allotment_id: allotmentId, list_id: id, task_id: taskId } },
        });
        if (error) throw new Error(failure(error, "Could not take that off the list"));
      },
      onSuccess: refresh,
    }),
  };
}

// The list the quick "add to list" buttons use. Kept in localStorage when it works (it can be blocked or
// empty), and in memory otherwise; every user of the hook is told when it changes.
const memory = new Map<string, string>();
const listeners = new Set<() => void>();
const storeKey = (allotmentId: number) => `allotment:${allotmentId}:day-list`;

function readSelected(allotmentId: number): number | null {
  const key = storeKey(allotmentId);
  let raw = memory.get(key) ?? null;
  if (raw === null) {
    try {
      raw = localStorage.getItem(key);
    } catch {
      raw = null;
    }
  }
  const n = raw === null ? NaN : Number(raw);
  return Number.isInteger(n) && n > 0 ? n : null;
}

export function useSelectedList(allotmentId: number): [number | null, (id: number | null) => void] {
  const selected = useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => readSelected(allotmentId),
  );
  const set = useCallback(
    (id: number | null) => {
      const key = storeKey(allotmentId);
      if (id === null) memory.delete(key);
      else memory.set(key, String(id));
      try {
        if (id === null) localStorage.removeItem(key);
        else localStorage.setItem(key, String(id));
      } catch {
        /* memory copy is enough */
      }
      listeners.forEach((l) => l());
    },
    [allotmentId],
  );
  return [selected, set];
}
