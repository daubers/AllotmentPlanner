import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components } from "../api/schema";
import type { Task } from "./group";

export type NewTask = components["schemas"]["TaskIn"];

const path = (allotmentId: number) => ({ path: { allotment_id: allotmentId } });
const taskPath = (allotmentId: number, taskId: number) => ({
  path: { allotment_id: allotmentId, task_id: taskId },
});

/** All tasks for an allotment; one cache shared by the Tasks page and the map. */
export function useTasks(allotmentId: number) {
  return useQuery({
    queryKey: ["tasks", allotmentId],
    queryFn: async (): Promise<Task[]> =>
      (await api.GET("/api/v1/allotments/{allotment_id}/tasks", { params: path(allotmentId) })).data ?? [],
  });
}

export type FeatureOption = { id: number; name: string; kind: string };

export function useFeatureOptions(allotmentId: number) {
  return useQuery({
    queryKey: ["feature-options", allotmentId],
    queryFn: async (): Promise<FeatureOption[]> => {
      const { data } = await api.GET("/api/v1/allotments/{allotment_id}/features", {
        params: path(allotmentId),
      });
      return (data?.features ?? []).map((f) => {
        const feature = f as { id: number; properties: { name?: string; kind?: string } };
        return { id: feature.id, name: feature.properties.name || `Unnamed ${feature.properties.kind}`, kind: feature.properties.kind ?? "other" };
      });
    },
  });
}

export function useTaskActions(allotmentId: number) {
  const qc = useQueryClient();
  const refresh = () => qc.invalidateQueries({ queryKey: ["tasks", allotmentId] });
  return {
    create: useMutation({
      mutationFn: async (body: NewTask) => {
        const { data, error } = await api.POST("/api/v1/allotments/{allotment_id}/tasks", {
          params: path(allotmentId),
          body,
        });
        if (!data) throw new Error((error as { message?: string })?.message ?? "Could not create task");
        return data;
      },
      onSuccess: refresh,
    }),
    complete: useMutation({
      mutationFn: (id: number) =>
        api.POST("/api/v1/allotments/{allotment_id}/tasks/{task_id}/complete", { params: taskPath(allotmentId, id) }),
      onSuccess: refresh,
    }),
    reopen: useMutation({
      mutationFn: (id: number) =>
        api.POST("/api/v1/allotments/{allotment_id}/tasks/{task_id}/reopen", { params: taskPath(allotmentId, id) }),
      onSuccess: refresh,
    }),
    remove: useMutation({
      mutationFn: (id: number) =>
        api.DELETE("/api/v1/allotments/{allotment_id}/tasks/{task_id}", { params: taskPath(allotmentId, id) }),
      onSuccess: refresh,
    }),
  };
}

export function useTodo(allotmentId: number, date: string, includeUndated: boolean) {
  return useQuery({
    queryKey: ["todo", allotmentId, date, includeUndated],
    queryFn: async () =>
      (
        await api.GET("/api/v1/allotments/{allotment_id}/todo", {
          params: { path: { allotment_id: allotmentId }, query: { date, include_undated: includeUndated } },
        })
      ).data,
  });
}
