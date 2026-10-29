import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components } from "../api/schema";
import { ringOf, type LonLat } from "./geometry";

export type Planting = components["schemas"]["Planting"];
export type PlantingStatus = NonNullable<components["schemas"]["PlantingPatch"]["status"]>;
export type Bed = { id: number; name: string; ring: LonLat[] };

export const STATUSES: [PlantingStatus, string][] = [
  ["sown", "Sown"],
  ["growing", "Growing"],
  ["harvesting", "Harvesting"],
  ["finished", "Finished"],
  ["failed", "Failed"],
];
export const STATUS_LABEL = Object.fromEntries(STATUSES) as Record<string, string>;

const path = (allotmentId: number) => ({ path: { allotment_id: allotmentId } });
const message = (error: unknown, fallback: string) => (error as { message?: string } | undefined)?.message ?? fallback;

/** The beds drawn on the map (areas, not lines or points): the only places a planting can go. */
export function useBeds(allotmentId: number) {
  return useQuery({
    queryKey: ["beds", allotmentId],
    queryFn: async (): Promise<Bed[]> => {
      const { data } = await api.GET("/api/v1/allotments/{allotment_id}/features", { params: path(allotmentId) });
      return (data?.features ?? [])
        .map((f) => f as { id: number; geometry: { type: string; coordinates?: unknown }; properties: { name?: string; kind?: string } })
        .filter((f) => f.properties.kind === "bed" && f.geometry.type === "Polygon")
        .map((f) => ({ id: f.id, name: f.properties.name || `Bed ${f.id}`, ring: ringOf(f.geometry) }));
    },
  });
}

export type PlantingFilters = { featureId?: number; packetId?: number; growing?: boolean };

export function usePlantings(allotmentId: number, filters: PlantingFilters = {}) {
  return useQuery({
    queryKey: ["plantings", allotmentId, filters],
    queryFn: async (): Promise<Planting[]> =>
      (
        await api.GET("/api/v1/allotments/{allotment_id}/plantings", {
          params: { ...path(allotmentId), query: { feature_id: filters.featureId, packet_id: filters.packetId, growing: filters.growing } },
        })
      ).data ?? [],
    placeholderData: keepPreviousData,
  });
}

export function usePlantingActions(allotmentId: number) {
  const qc = useQueryClient();
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["plantings", allotmentId] });
    void qc.invalidateQueries({ queryKey: ["trays", allotmentId] });
    void qc.invalidateQueries({ queryKey: ["tray", allotmentId] });
  };
  const one = (id: number) => ({ path: { allotment_id: allotmentId, planting_id: id } });
  return {
    refresh,
    create: useMutation({
      mutationFn: async (body: components["schemas"]["PlantingIn"]): Promise<Planting> => {
        const { data, error } = await api.POST("/api/v1/allotments/{allotment_id}/plantings", { params: path(allotmentId), body });
        if (!data) throw new Error(message(error, "Couldn't add the planting"));
        return data;
      },
      onSuccess: refresh,
    }),
    patch: useMutation({
      mutationFn: async ({ id, ...body }: components["schemas"]["PlantingPatch"] & { id: number }): Promise<Planting> => {
        const { data, error } = await api.PATCH("/api/v1/allotments/{allotment_id}/plantings/{planting_id}", { params: one(id), body });
        if (!data) throw new Error(message(error, "Couldn't save the planting"));
        return data;
      },
      onSuccess: refresh,
    }),
    remove: useMutation({
      mutationFn: async (id: number) => {
        const { error } = await api.DELETE("/api/v1/allotments/{allotment_id}/plantings/{planting_id}", { params: one(id) });
        if (error) throw new Error(message(error, "Couldn't delete the planting"));
      },
      onSuccess: refresh,
    }),
  };
}

export function usePlantOut(allotmentId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: { trayId: number } & components["schemas"]["PlantOut"]) => {
      const { trayId, ...body } = input;
      const { data, error } = await api.POST("/api/v1/allotments/{allotment_id}/trays/{tray_id}/plant-out", {
        params: { path: { allotment_id: allotmentId, tray_id: trayId } },
        body,
      });
      if (!data) throw new Error(message(error, "Couldn't plant those out"));
      return data;
    },
    onSuccess: () => {
      for (const key of ["plantings", "trays", "tray"]) void qc.invalidateQueries({ queryKey: [key, allotmentId] });
    },
  });
}
