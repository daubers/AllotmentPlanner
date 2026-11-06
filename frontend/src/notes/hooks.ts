import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components } from "../api/schema";

export type Note = components["schemas"]["FeatureNote"];
export type NewNote = { feature_id: number; body: string; noted_at?: string | null };
export type NotePatch = { body?: string; noted_at?: string };

const path = (allotmentId: number) => ({ path: { allotment_id: allotmentId } });
const failure = (error: unknown, fallback: string) => (error as { message?: string } | undefined)?.message ?? fallback;

/** Notes, newest first: all of the allotment's, or one feature's. */
export function useNotes(allotmentId: number, featureId?: number | null) {
  return useQuery({
    queryKey: ["notes", allotmentId, featureId ?? null],
    queryFn: async (): Promise<Note[]> => {
      const query = featureId == null ? {} : { feature_id: featureId };
      return (await api.GET("/api/v1/allotments/{allotment_id}/notes", { params: { ...path(allotmentId), query } })).data ?? [];
    },
  });
}

export function useNoteActions(allotmentId: number) {
  const qc = useQueryClient();
  const refresh = () => void qc.invalidateQueries({ queryKey: ["notes", allotmentId] });
  return {
    create: useMutation({
      mutationFn: async (body: NewNote) => {
        const { data, error } = await api.POST("/api/v1/allotments/{allotment_id}/notes", { params: path(allotmentId), body });
        if (!data) throw new Error(failure(error, "Could not save note"));
        return data;
      },
      onSuccess: refresh,
    }),
    update: useMutation({
      mutationFn: async ({ id, body }: { id: number; body: NotePatch }) => {
        const { data, error } = await api.PATCH("/api/v1/allotments/{allotment_id}/notes/{note_id}", {
          params: { path: { allotment_id: allotmentId, note_id: id } },
          body,
        });
        if (!data) throw new Error(failure(error, "Could not save note"));
        return data;
      },
      onSuccess: refresh,
    }),
    remove: useMutation({
      mutationFn: async (id: number) => {
        const { error } = await api.DELETE("/api/v1/allotments/{allotment_id}/notes/{note_id}", {
          params: { path: { allotment_id: allotmentId, note_id: id } },
        });
        if (error) throw new Error(failure(error, "Could not delete note"));
      },
      onSuccess: refresh,
    }),
  };
}
