import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components } from "../api/schema";
import type { Media } from "./group";

type Patch = components["schemas"]["MediaPatch"];

const path = (allotmentId: number) => ({ path: { allotment_id: allotmentId } });
const mediaPath = (allotmentId: number, id: number) => ({ path: { allotment_id: allotmentId, media_id: id } });

export type MediaFilters = { featureId?: number; kind?: "photo" | "video" };

/** Media for an allotment. While anything is still being processed, poll until it settles. */
export function useMedia(allotmentId: number, filters: MediaFilters = {}) {
  return useQuery({
    queryKey: ["media", allotmentId, filters],
    queryFn: async (): Promise<Media[]> =>
      (
        await api.GET("/api/v1/allotments/{allotment_id}/media", {
          params: { ...path(allotmentId), query: { feature_id: filters.featureId, kind: filters.kind, limit: 500 } },
        })
      ).data ?? [],
    placeholderData: keepPreviousData, // no empty flash while a filter change loads
    refetchInterval: (q) => (q.state.data?.some((m) => m.status === "pending") ? 2000 : false),
  });
}

/** multipart/form-data body; the browser sets the boundary header itself. */
function toFormData(body: Record<string, unknown>): FormData {
  const form = new FormData();
  for (const [key, value] of Object.entries(body)) {
    if (value === undefined || value === null || value === "") continue;
    form.append(key, value as string | Blob);
  }
  return form;
}

export type UploadInput = { file: File; featureId?: number | null; caption?: string };

export async function uploadMedia(allotmentId: number, { file, featureId, caption }: UploadInput): Promise<Media> {
  const { data, error, response } = await api.POST("/api/v1/allotments/{allotment_id}/media", {
    params: path(allotmentId),
    body: { file: file as unknown as string, feature_id: featureId ?? undefined, caption },
    bodySerializer: (b) => toFormData(b as Record<string, unknown>),
  });
  if (!data) {
    const message = (error as { message?: string } | undefined)?.message;
    throw new Error(message ?? (response.status === 413 ? "File is too large" : `Upload failed (${response.status})`));
  }
  return data;
}

export function useMediaActions(allotmentId: number) {
  const qc = useQueryClient();
  const refresh = () => qc.invalidateQueries({ queryKey: ["media", allotmentId] });
  return {
    refresh,
    patch: useMutation({
      mutationFn: async ({ id, ...body }: Patch & { id: number }) =>
        api.PATCH("/api/v1/allotments/{allotment_id}/media/{media_id}", { params: mediaPath(allotmentId, id), body }),
      onSuccess: refresh,
    }),
    remove: useMutation({
      mutationFn: (id: number) =>
        api.DELETE("/api/v1/allotments/{allotment_id}/media/{media_id}", { params: mediaPath(allotmentId, id) }),
      onSuccess: refresh,
    }),
    reprocess: useMutation({
      mutationFn: (id: number) =>
        api.POST("/api/v1/allotments/{allotment_id}/media/{media_id}/reprocess", { params: mediaPath(allotmentId, id) }),
      onSuccess: refresh,
    }),
  };
}
