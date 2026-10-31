import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components } from "../api/schema";
import type { Task } from "./group";

export type NewTask = components["schemas"]["TaskIn"];
export type TaskPatch = components["schemas"]["TaskPatch"];
export type Member = components["schemas"]["Member"];
export type BulkAction = components["schemas"]["TaskBulk"]["action"];

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

export function useMembers(allotmentId: number) {
  return useQuery({
    queryKey: ["members", allotmentId],
    queryFn: async (): Promise<Member[]> =>
      (await api.GET("/api/v1/allotments/{allotment_id}/members", { params: path(allotmentId) })).data ?? [],
  });
}

const failure = (error: unknown, fallback: string) => (error as { message?: string } | undefined)?.message ?? fallback;

export function useTaskActions(allotmentId: number) {
  const qc = useQueryClient();
  // The Today sheet is built from the same tasks, so it is refreshed with the list.
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["tasks", allotmentId] });
    void qc.invalidateQueries({ queryKey: ["todo", allotmentId] });
  };
  /** Show a tick or untick at once; the refresh that follows settles it (or puts it back on failure). */
  const optimistic = (status: "done" | "todo") => async (id: number) => {
    await qc.cancelQueries({ queryKey: ["tasks", allotmentId] });
    const before = qc.getQueryData<Task[]>(["tasks", allotmentId]);
    qc.setQueryData<Task[]>(["tasks", allotmentId], (list) =>
      list?.map((t) => (t.id === id ? { ...t, status, completed_at: status === "done" ? new Date().toISOString() : null } : t)),
    );
    return { before };
  };
  const rollback = (_e: unknown, _id: number, ctx?: { before?: Task[] }) => {
    if (ctx?.before) qc.setQueryData(["tasks", allotmentId], ctx.before);
  };
  return {
    create: useMutation({
      mutationFn: async (body: NewTask) => {
        const { data, error } = await api.POST("/api/v1/allotments/{allotment_id}/tasks", {
          params: path(allotmentId),
          body,
        });
        if (!data) throw new Error(failure(error, "Could not create task"));
        return data;
      },
      onSuccess: refresh,
    }),
    update: useMutation({
      mutationFn: async ({ id, body }: { id: number; body: TaskPatch }) => {
        const { data, error } = await api.PATCH("/api/v1/allotments/{allotment_id}/tasks/{task_id}", {
          params: taskPath(allotmentId, id),
          body,
        });
        if (!data) throw new Error(failure(error, "Could not save task"));
        return data;
      },
      onSuccess: refresh,
    }),
    complete: useMutation({
      mutationFn: (id: number) =>
        api.POST("/api/v1/allotments/{allotment_id}/tasks/{task_id}/complete", { params: taskPath(allotmentId, id) }),
      onMutate: optimistic("done"),
      onError: rollback,
      onSettled: refresh,
    }),
    reopen: useMutation({
      mutationFn: (id: number) =>
        api.POST("/api/v1/allotments/{allotment_id}/tasks/{task_id}/reopen", { params: taskPath(allotmentId, id) }),
      onMutate: optimistic("todo"),
      onError: rollback,
      onSettled: refresh,
    }),
    remove: useMutation({
      mutationFn: (id: number) =>
        api.DELETE("/api/v1/allotments/{allotment_id}/tasks/{task_id}", { params: taskPath(allotmentId, id) }),
      onSuccess: refresh,
    }),
    bulk: useMutation({
      mutationFn: async (body: { ids: number[]; action: BulkAction; due_date?: string | null }) => {
        const { data, error } = await api.POST("/api/v1/allotments/{allotment_id}/tasks/bulk", {
          params: path(allotmentId),
          body,
        });
        if (!data) throw new Error(failure(error, "Could not change those tasks"));
        return data;
      },
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
