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
    // Day lists show task state too (done counts, the sheet).
    void qc.invalidateQueries({ queryKey: ["day-lists", allotmentId] });
    void qc.invalidateQueries({ queryKey: ["day-list-sheet", allotmentId] });
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

export type Suggestion = components["schemas"]["TaskSuggestion"];
export type SuggestFor = { kind: "tray" | "planting"; id: number };

/** The jobs the packet's dates suggest for a tray or planting, and a way to add them all. */
export function useSuggestedTasks(allotmentId: number, target: SuggestFor, enabled: boolean) {
  const qc = useQueryClient();
  const key = ["suggested-tasks", allotmentId, target.kind, target.id];
  const suggestions = useQuery({
    queryKey: key,
    enabled,
    queryFn: async (): Promise<Suggestion[]> => {
      const params = { path: { allotment_id: allotmentId } };
      if (target.kind === "tray") {
        return (await api.GET("/api/v1/allotments/{allotment_id}/trays/{tray_id}/suggested-tasks", { params: { path: { ...params.path, tray_id: target.id } } })).data ?? [];
      }
      return (await api.GET("/api/v1/allotments/{allotment_id}/plantings/{planting_id}/suggested-tasks", { params: { path: { ...params.path, planting_id: target.id } } })).data ?? [];
    },
  });
  const add = useMutation({
    /** `equipment` maps a suggestion's key to the equipment ids to put on its task; nothing is attached unless named. */
    mutationFn: async (equipment?: Record<string, number[]>) => {
      const path = { allotment_id: allotmentId };
      const body = { equipment: equipment ?? null };
      const { data, error } =
        target.kind === "tray"
          ? await api.POST("/api/v1/allotments/{allotment_id}/trays/{tray_id}/suggested-tasks", { params: { path: { ...path, tray_id: target.id } }, body })
          : await api.POST("/api/v1/allotments/{allotment_id}/plantings/{planting_id}/suggested-tasks", { params: { path: { ...path, planting_id: target.id } }, body });
      if (!data) throw new Error(failure(error, "Could not add the tasks"));
      return data;
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: key });
      void qc.invalidateQueries({ queryKey: ["tasks", allotmentId] });
      void qc.invalidateQueries({ queryKey: ["todo", allotmentId] });
    },
  });
  return { suggestions, add };
}

export type TaskSeries = components["schemas"]["TaskSeries"];
export type NewSeries = components["schemas"]["TaskSeriesIn"];
export type SeriesPatch = components["schemas"]["TaskSeriesPatch"];

const seriesPath = (allotmentId: number, seriesId: number) => ({ path: { allotment_id: allotmentId, series_id: seriesId } });

/** The repeating schedules (each makes its tasks ahead of time). */
export function useTaskSeries(allotmentId: number) {
  return useQuery({
    queryKey: ["task-series", allotmentId],
    queryFn: async (): Promise<TaskSeries[]> =>
      (await api.GET("/api/v1/allotments/{allotment_id}/task-series", { params: path(allotmentId) })).data ?? [],
  });
}

export function useSeriesActions(allotmentId: number) {
  const qc = useQueryClient();
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["task-series", allotmentId] });
    void qc.invalidateQueries({ queryKey: ["tasks", allotmentId] });
    void qc.invalidateQueries({ queryKey: ["todo", allotmentId] });
  };
  return {
    create: useMutation({
      mutationFn: async (body: NewSeries): Promise<TaskSeries> => {
        const { data, error } = await api.POST("/api/v1/allotments/{allotment_id}/task-series", { params: path(allotmentId), body });
        if (!data) throw new Error(failure(error, "Could not set up the schedule"));
        return data;
      },
      onSuccess: refresh,
    }),
    update: useMutation({
      mutationFn: async ({ id, body }: { id: number; body: SeriesPatch }): Promise<TaskSeries> => {
        const { data, error } = await api.PATCH("/api/v1/allotments/{allotment_id}/task-series/{series_id}", {
          params: seriesPath(allotmentId, id),
          body,
        });
        if (!data) throw new Error(failure(error, "Could not change the schedule"));
        return data;
      },
      onSuccess: refresh,
    }),
    remove: useMutation({
      mutationFn: async (id: number) => {
        const { error } = await api.DELETE("/api/v1/allotments/{allotment_id}/task-series/{series_id}", { params: seriesPath(allotmentId, id) });
        if (error) throw new Error(failure(error, "Could not stop the schedule"));
      },
      onSuccess: refresh,
    }),
  };
}
