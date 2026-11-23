import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components } from "../api/schema";

export type Equipment = components["schemas"]["Equipment"];
export type EquipmentInput = components["schemas"]["EquipmentIn"];
export type EquipmentPatch = components["schemas"]["EquipmentPatch"];
export type EquipmentKind = components["schemas"]["EquipmentKind"];
export type EquipmentStatus = NonNullable<Equipment["status"]>;
/** One of the known kinds, e.g. "spade". */
export type KindKey = NonNullable<EquipmentInput["kind"]>;

export const STATUS_LABEL: Record<EquipmentStatus, string> = { in_service: "In service", out_of_action: "Out of action" };

export type EquipmentFilters = { q?: string; kind?: KindKey; status?: EquipmentStatus };

const path = (allotmentId: number) => ({ path: { allotment_id: allotmentId } });
const one = (allotmentId: number, id: number) => ({ path: { allotment_id: allotmentId, equipment_id: id } });
const message = (error: unknown, fallback: string) => (error as { message?: string } | undefined)?.message ?? fallback;

export function useEquipmentList(allotmentId: number, filters: EquipmentFilters = {}) {
  return useQuery({
    queryKey: ["equipment", allotmentId, filters],
    queryFn: async (): Promise<Equipment[]> =>
      (
        await api.GET("/api/v1/allotments/{allotment_id}/equipment", {
          params: { ...path(allotmentId), query: { ...filters, q: filters.q?.trim() || undefined } },
        })
      ).data ?? [],
    placeholderData: keepPreviousData,
  });
}

export function useEquipmentItem(allotmentId: number, id: number) {
  return useQuery({
    queryKey: ["equipment-item", allotmentId, id],
    queryFn: async (): Promise<Equipment | undefined> =>
      (await api.GET("/api/v1/allotments/{allotment_id}/equipment/{equipment_id}", { params: one(allotmentId, id) })).data,
  });
}

/** The kinds of equipment the app knows (spade, dibber, cloche...). They never change while the app is open. */
export function useEquipmentKinds() {
  return useQuery({
    queryKey: ["equipment-kinds"],
    queryFn: async (): Promise<EquipmentKind[]> => (await api.GET("/api/v1/equipment-kinds")).data ?? [],
    staleTime: Infinity,
  });
}

export function useEquipmentActions(allotmentId: number) {
  const qc = useQueryClient();
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["equipment", allotmentId] });
    void qc.invalidateQueries({ queryKey: ["equipment-item", allotmentId] });
  };
  return {
    refresh,
    create: useMutation({
      mutationFn: async (body: EquipmentInput): Promise<Equipment> => {
        const { data, error } = await api.POST("/api/v1/allotments/{allotment_id}/equipment", { params: path(allotmentId), body });
        if (!data) throw new Error(message(error, "Couldn't add that"));
        return data;
      },
      onSuccess: refresh,
    }),
    patch: useMutation({
      mutationFn: async ({ id, ...body }: EquipmentPatch & { id: number }): Promise<Equipment> => {
        const { data, error } = await api.PATCH("/api/v1/allotments/{allotment_id}/equipment/{equipment_id}", {
          params: one(allotmentId, id),
          body,
        });
        if (!data) throw new Error(message(error, "Couldn't save the changes"));
        return data;
      },
      onSuccess: refresh,
    }),
    remove: useMutation({
      mutationFn: async (id: number) => {
        const { error } = await api.DELETE("/api/v1/allotments/{allotment_id}/equipment/{equipment_id}", { params: one(allotmentId, id) });
        if (error) throw new Error(message(error, "Couldn't delete it"));
      },
      onSuccess: refresh,
    }),
  };
}
