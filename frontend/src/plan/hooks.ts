import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components } from "../api/schema";

export type Plan = components["schemas"]["Plan"];
export type PlanBed = components["schemas"]["PlanBed"];
export type PlanItem = components["schemas"]["PlanItem"];
export type PlanItemInput = components["schemas"]["PlanItemIn"];
export type PlanItemPatch = components["schemas"]["PlanItemPatch"];
export type Crop = components["schemas"]["Crop"];
export type PlanTaskSuggestion = components["schemas"]["PlanTaskSuggestion"];

const path = (allotmentId: number) => ({ path: { allotment_id: allotmentId } });
const itemPath = (allotmentId: number, itemId: number) => ({ path: { allotment_id: allotmentId, item_id: itemId } });
const failure = (error: unknown, fallback: string) => (error as { message?: string } | undefined)?.message ?? fallback;

/** Every bed with its plan items between two dates (YYYY-MM-DD), and when each is overbooked. */
export function usePlan(allotmentId: number, from: string, to: string) {
  return useQuery({
    queryKey: ["plan", allotmentId, from, to],
    queryFn: async (): Promise<Plan | undefined> =>
      (await api.GET("/api/v1/allotments/{allotment_id}/plan", { params: { ...path(allotmentId), query: { from, to } } })).data,
    placeholderData: keepPreviousData,
  });
}

/** One plan item, e.g. the crop being planted from the Plan page. Pass null to ask for nothing. */
export function usePlanItem(allotmentId: number, itemId: number | null) {
  return useQuery({
    queryKey: ["plan-item", allotmentId, itemId],
    enabled: itemId !== null,
    queryFn: async (): Promise<PlanItem | undefined> =>
      (await api.GET("/api/v1/allotments/{allotment_id}/plan-items/{item_id}", { params: itemPath(allotmentId, itemId!) })).data,
  });
}

/** The built-in crops. They never change while the app is open. */
export function useCrops() {
  return useQuery({
    queryKey: ["crops"],
    queryFn: async (): Promise<Crop[]> => (await api.GET("/api/v1/crops", { params: { query: {} } })).data ?? [],
    staleTime: Infinity,
  });
}

export function usePlanActions(allotmentId: number) {
  const qc = useQueryClient();
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["plan", allotmentId] });
    void qc.invalidateQueries({ queryKey: ["plan-tasks", allotmentId] }); // edits can make made tasks stale
    void qc.invalidateQueries({ queryKey: ["plan-item", allotmentId] });
  };
  return {
    create: useMutation({
      mutationFn: async (body: PlanItemInput): Promise<PlanItem> => {
        const { data, error } = await api.POST("/api/v1/allotments/{allotment_id}/plan-items", { params: path(allotmentId), body });
        if (!data) throw new Error(failure(error, "Could not add that to the plan"));
        return data;
      },
      onSuccess: refresh,
    }),
    succession: useMutation({
      mutationFn: async (body: { item: PlanItemInput; interval_days: number; count: number }): Promise<PlanItem[]> => {
        const { data, error } = await api.POST("/api/v1/allotments/{allotment_id}/plan-items/successions", {
          params: path(allotmentId),
          body,
        });
        if (!data) throw new Error(failure(error, "Could not plan the succession"));
        return data;
      },
      onSuccess: refresh,
    }),
    update: useMutation({
      mutationFn: async ({ id, body }: { id: number; body: PlanItemPatch }): Promise<PlanItem> => {
        const { data, error } = await api.PATCH("/api/v1/allotments/{allotment_id}/plan-items/{item_id}", {
          params: itemPath(allotmentId, id),
          body,
        });
        if (!data) throw new Error(failure(error, "Could not save the change"));
        return data;
      },
      onSuccess: refresh,
    }),
    remove: useMutation({
      mutationFn: async (id: number) => {
        const { error } = await api.DELETE("/api/v1/allotments/{allotment_id}/plan-items/{item_id}", {
          params: itemPath(allotmentId, id),
        });
        if (error) throw new Error(failure(error, "Could not remove it"));
      },
      onSuccess: refresh,
    }),
  };
}

/** The jobs the plan implies (sow, plant out, clear the bed), and how many tasks made earlier are out of date. */
export function usePlanTasks(allotmentId: number, featureId: number | null) {
  return useQuery({
    queryKey: ["plan-tasks", allotmentId, featureId],
    queryFn: async () =>
      (
        await api.GET("/api/v1/allotments/{allotment_id}/plan/task-suggestions", {
          params: { ...path(allotmentId), query: featureId ? { feature_id: featureId } : {} },
        })
      ).data,
  });
}

export function usePlanTaskActions(allotmentId: number) {
  const qc = useQueryClient();
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["plan-tasks", allotmentId] });
    void qc.invalidateQueries({ queryKey: ["tasks", allotmentId] });
    void qc.invalidateQueries({ queryKey: ["todo", allotmentId] });
  };
  return {
    add: useMutation({
      mutationFn: async ({ keys, featureId }: { keys?: string[]; featureId?: number | null }) => {
        const { data, error } = await api.POST("/api/v1/allotments/{allotment_id}/plan/tasks", {
          params: path(allotmentId),
          body: { keys: keys ?? null, feature_id: featureId ?? null },
        });
        if (!data) throw new Error(failure(error, "Could not add those tasks"));
        return data;
      },
      onSuccess: refresh,
    }),
    sync: useMutation({
      mutationFn: async (featureId?: number | null) => {
        const { data, error } = await api.POST("/api/v1/allotments/{allotment_id}/plan/tasks/sync", {
          params: path(allotmentId),
          body: { feature_id: featureId ?? null },
        });
        if (!data) throw new Error(failure(error, "Could not update the tasks"));
        return data;
      },
      onSuccess: refresh,
    }),
  };
}
