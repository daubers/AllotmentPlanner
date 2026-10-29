import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, authHeader } from "../api/client";
import type { components } from "../api/schema";
import { anyActive, type MapJob, type MapLayer } from "./status";

export type NewMapJob = components["schemas"]["MapJobIn"];
type LayerPatch = components["schemas"]["MapLayerPatch"];

const path = (allotmentId: number) => ({ path: { allotment_id: allotmentId } });
const message = (error: unknown, fallback: string) => (error as { message?: string } | undefined)?.message ?? fallback;

/** Layers for the map and the Layers page. Tile links are signed and expire, so refresh hourly. */
export function useLayers(allotmentId: number) {
  return useQuery({
    queryKey: ["layers", allotmentId],
    queryFn: async (): Promise<MapLayer[]> =>
      (await api.GET("/api/v1/allotments/{allotment_id}/layers", { params: path(allotmentId) })).data ?? [],
    staleTime: 30 * 60 * 1000,
    refetchInterval: 60 * 60 * 1000,
  });
}

/** Recent builds; refreshes every few seconds while one is queued or running. */
export function useMapJobs(allotmentId: number, enabled = true) {
  return useQuery({
    queryKey: ["map-jobs", allotmentId],
    enabled,
    queryFn: async (): Promise<MapJob[]> =>
      (await api.GET("/api/v1/allotments/{allotment_id}/map-jobs", { params: path(allotmentId) })).data ?? [],
    refetchInterval: (q) => (anyActive(q.state.data) ? 3000 : false),
  });
}

/** One job with its log; used when a row is expanded. */
export function useMapJobDetail(allotmentId: number, jobId: number | null, active: boolean) {
  return useQuery({
    queryKey: ["map-job", allotmentId, jobId],
    enabled: jobId != null,
    queryFn: async (): Promise<MapJob | undefined> =>
      (await api.GET("/api/v1/allotments/{allotment_id}/map-jobs/{job_id}", { params: { path: { allotment_id: allotmentId, job_id: jobId! } } })).data,
    refetchInterval: active ? 4000 : false,
  });
}

export function useMapActions(allotmentId: number) {
  const qc = useQueryClient();
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["layers", allotmentId] });
    void qc.invalidateQueries({ queryKey: ["map-jobs", allotmentId] });
  };
  const jobPath = (jobId: number) => ({ path: { allotment_id: allotmentId, job_id: jobId } });
  return {
    build: useMutation({
      mutationFn: async (body: NewMapJob) => {
        const { data, error } = await api.POST("/api/v1/allotments/{allotment_id}/map-jobs", { params: path(allotmentId), body });
        if (!data) throw new Error(message(error, "Could not start the map"));
        return data;
      },
      onSuccess: refresh,
    }),
    cancel: useMutation({
      mutationFn: async (jobId: number) => {
        const { data, error } = await api.POST("/api/v1/allotments/{allotment_id}/map-jobs/{job_id}/cancel", { params: jobPath(jobId) });
        if (!data) throw new Error(message(error, "Could not cancel"));
      },
      onSuccess: refresh,
    }),
    removeJob: useMutation({
      mutationFn: async (jobId: number) => {
        const { error, response } = await api.DELETE("/api/v1/allotments/{allotment_id}/map-jobs/{job_id}", { params: jobPath(jobId) });
        if (!response.ok) throw new Error(message(error, "Could not remove"));
      },
      onSuccess: refresh,
    }),
    patchLayer: useMutation({
      mutationFn: async ({ id, ...body }: LayerPatch & { id: number }) => {
        const { data, error } = await api.PATCH("/api/v1/allotments/{allotment_id}/layers/{layer_id}", {
          params: { path: { allotment_id: allotmentId, layer_id: id } },
          body,
        });
        if (!data) throw new Error(message(error, "Could not update the layer"));
      },
      onSuccess: refresh,
    }),
    removeLayer: useMutation({
      mutationFn: async (id: number) => {
        const { error, response } = await api.DELETE("/api/v1/allotments/{allotment_id}/layers/{layer_id}", {
          params: { path: { allotment_id: allotmentId, layer_id: id } },
        });
        if (!response.ok) throw new Error(message(error, "Could not delete the layer"));
      },
      onSuccess: refresh,
    }),
  };
}

export type GpxOutline = components["schemas"]["BoundaryFromGpx"];

/** Ask the server what outline a GPX trace gives. Nothing is stored: the result is checked, then sent with the build. */
export async function readGpx(allotmentId: number, file: File): Promise<GpxOutline> {
  const form = new FormData();
  form.append("file", file);
  const header = await authHeader();
  const res = await fetch(`/api/v1/allotments/${allotmentId}/boundary-from-gpx`, {
    method: "POST",
    headers: { Accept: "application/json", ...(header ? { Authorization: header } : {}) },
    body: form,
  });
  const body = (await res.json().catch(() => null)) as (GpxOutline & { message?: string }) | null;
  if (!res.ok || !body) throw new Error(body?.message ?? "Couldn't read that file");
  return body;
}
