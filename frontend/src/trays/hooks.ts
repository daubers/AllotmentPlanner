import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components } from "../api/schema";
import type { Tray, TraySummary } from "./grid";

export type TrayInput = components["schemas"]["TrayIn"];
export type TrayPatch = components["schemas"]["TrayPatch"];
export type CellChange = components["schemas"]["CellSet"];
export type TrayFilters = { status?: "active" | "planted_out" | "finished"; packetId?: number };

const path = (allotmentId: number) => ({ path: { allotment_id: allotmentId } });
const trayPath = (allotmentId: number, id: number) => ({ path: { allotment_id: allotmentId, tray_id: id } });
const message = (error: unknown, fallback: string) => (error as { message?: string } | undefined)?.message ?? fallback;

export function useTrays(allotmentId: number, filters: TrayFilters = {}) {
  return useQuery({
    queryKey: ["trays", allotmentId, filters],
    queryFn: async (): Promise<TraySummary[]> =>
      (
        await api.GET("/api/v1/allotments/{allotment_id}/trays", {
          params: { ...path(allotmentId), query: { status: filters.status, packet_id: filters.packetId } },
        })
      ).data ?? [],
    placeholderData: keepPreviousData,
  });
}

export function useTray(allotmentId: number, id: number) {
  return useQuery({
    queryKey: ["tray", allotmentId, id],
    queryFn: async (): Promise<Tray | undefined> =>
      (await api.GET("/api/v1/allotments/{allotment_id}/trays/{tray_id}", { params: trayPath(allotmentId, id) })).data,
    refetchInterval: (q) => (q.state.data?.photos?.some((m) => m.status === "pending") ? 2000 : false),
  });
}

export function useTrayActions(allotmentId: number) {
  const qc = useQueryClient();
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["trays", allotmentId] });
    void qc.invalidateQueries({ queryKey: ["tray", allotmentId] });
  };
  return {
    refresh,
    create: useMutation({
      mutationFn: async (body: TrayInput): Promise<Tray> => {
        const { data, error } = await api.POST("/api/v1/allotments/{allotment_id}/trays", { params: path(allotmentId), body });
        if (!data) throw new Error(message(error, "Couldn't add the tray"));
        return data;
      },
      onSuccess: refresh,
    }),
    patch: useMutation({
      mutationFn: async ({ id, ...body }: TrayPatch & { id: number }): Promise<Tray> => {
        const { data, error } = await api.PATCH("/api/v1/allotments/{allotment_id}/trays/{tray_id}", { params: trayPath(allotmentId, id), body });
        if (!data) throw new Error(message(error, "Couldn't save the tray"));
        return data;
      },
      onSuccess: refresh,
    }),
    setCells: useMutation({
      mutationFn: async ({ id, cells, set }: { id: number; cells: { row: number; col: number }[]; set: CellChange }): Promise<Tray> => {
        const { data, error } = await api.PATCH("/api/v1/allotments/{allotment_id}/trays/{tray_id}/cells", {
          params: trayPath(allotmentId, id),
          body: { cells, set },
        });
        if (!data) throw new Error(message(error, "Couldn't change those cells"));
        return data;
      },
      onSuccess: refresh,
    }),
    remove: useMutation({
      mutationFn: async (id: number) => {
        const { error } = await api.DELETE("/api/v1/allotments/{allotment_id}/trays/{tray_id}", { params: trayPath(allotmentId, id) });
        if (error) throw new Error(message(error, "Couldn't delete the tray"));
      },
      onSuccess: refresh,
    }),
  };
}
