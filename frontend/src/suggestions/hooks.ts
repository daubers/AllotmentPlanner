import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components } from "../api/schema";
import type { Suggestion } from "./model";

type Patch = components["schemas"]["SuggestionPatch"];
type AcceptedFeature = components["schemas"]["Feature"];

const path = (allotmentId: number) => ({ path: { allotment_id: allotmentId } });
const message = (error: unknown, fallback: string) => (error as { message?: string } | undefined)?.message ?? fallback;

/** Pending suggestions for an allotment (editors only; others get none). */
export function useSuggestions(allotmentId: number, enabled: boolean) {
  return useQuery({
    queryKey: ["suggestions", allotmentId],
    enabled,
    queryFn: async (): Promise<Suggestion[]> =>
      (await api.GET("/api/v1/allotments/{allotment_id}/suggestions", { params: { ...path(allotmentId), query: { status: "pending" } } })).data ?? [],
  });
}

export function useSuggestionActions(allotmentId: number) {
  const qc = useQueryClient();
  const refresh = () => qc.invalidateQueries({ queryKey: ["suggestions", allotmentId] });
  return {
    patch: useMutation({
      mutationFn: async ({ id, ...body }: Patch & { id: number }) => {
        const { data, error } = await api.PATCH("/api/v1/allotments/{allotment_id}/suggestions/{suggestion_id}", {
          params: { path: { allotment_id: allotmentId, suggestion_id: id } },
          body,
        });
        if (!data) throw new Error(message(error, "Could not update the suggestion"));
        return data;
      },
      onSuccess: refresh,
    }),
    accept: useMutation({
      mutationFn: async (ids: number[]): Promise<AcceptedFeature[]> => {
        const { data, error } = await api.POST("/api/v1/allotments/{allotment_id}/suggestions/accept", { params: path(allotmentId), body: { ids } });
        if (!data) throw new Error(message(error, "Could not add them to the map"));
        return data;
      },
      onSuccess: refresh,
    }),
    dismiss: useMutation({
      mutationFn: async (ids: number[]) => {
        const { error, response } = await api.POST("/api/v1/allotments/{allotment_id}/suggestions/dismiss", { params: path(allotmentId), body: { ids } });
        if (!response.ok) throw new Error(message(error, "Could not dismiss them"));
      },
      onSuccess: refresh,
    }),
  };
}
