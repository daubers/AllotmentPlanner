import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components } from "../api/schema";

export type Equipment = components["schemas"]["Equipment"];
export type EquipmentInput = components["schemas"]["EquipmentIn"];
export type EquipmentPatch = components["schemas"]["EquipmentPatch"];
export type EquipmentKind = components["schemas"]["EquipmentKind"];
export type EquipmentSuggestion = components["schemas"]["EquipmentSuggestion"];
export type Booking = components["schemas"]["Booking"];
export type BookingConflict = components["schemas"]["BookingConflict"];
export type BookingInput = components["schemas"]["BookingIn"];
export type Maintenance = components["schemas"]["Maintenance"];
export type MaintenanceInput = components["schemas"]["MaintenanceIn"];
/** A piece of equipment as a task shows it. */
export type TaskEquipment = components["schemas"]["TaskEquipment"];
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

export type SuggestInput = { title: string; description: string; key?: string | null; featureId?: number | null; exclude: number[] };

/** Which of your equipment a job probably needs, from its wording (and, for generated tasks, its key). */
export function useEquipmentSuggestions(allotmentId: number, input: SuggestInput, enabled: boolean) {
  const title = input.title.trim();
  const exclude = [...input.exclude].sort((a, b) => a - b);
  return useQuery({
    queryKey: ["equipment-suggest", allotmentId, title, input.description, input.key ?? null, input.featureId ?? null, exclude],
    enabled: enabled && title.length >= 3,
    staleTime: 30_000,
    placeholderData: keepPreviousData,
    queryFn: async (): Promise<EquipmentSuggestion[]> =>
      (
        await api.POST("/api/v1/allotments/{allotment_id}/equipment/suggest", {
          params: path(allotmentId),
          body: { title, description: input.description, suggestion_key: input.key ?? null, feature_id: input.featureId ?? null, exclude_ids: exclude },
        })
      ).data ?? [],
  });
}

/** An item's maintenance: its schedules, when it is next due and when it was last serviced. */
export function useMaintenance(allotmentId: number, id: number) {
  return useQuery({
    queryKey: ["equipment-maintenance", allotmentId, id],
    queryFn: async (): Promise<Maintenance | undefined> =>
      (await api.GET("/api/v1/allotments/{allotment_id}/equipment/{equipment_id}/maintenance", { params: one(allotmentId, id) })).data,
  });
}

export function useMaintenanceActions(allotmentId: number, id: number) {
  const qc = useQueryClient();
  const refresh = () => {
    for (const key of ["equipment-maintenance", "equipment", "equipment-item", "tasks", "todo", "task-series"]) {
      void qc.invalidateQueries({ queryKey: [key, allotmentId] });
    }
  };
  return {
    schedule: useMutation({
      mutationFn: async (body: MaintenanceInput) => {
        const { data, error } = await api.POST("/api/v1/allotments/{allotment_id}/equipment/{equipment_id}/maintenance", {
          params: one(allotmentId, id),
          body,
        });
        if (!data) throw new Error(message(error, "Couldn't schedule that"));
        return data;
      },
      onSuccess: refresh,
    }),
    stop: useMutation({
      mutationFn: async (seriesId: number) => {
        const { error } = await api.DELETE("/api/v1/allotments/{allotment_id}/task-series/{series_id}", {
          params: { path: { allotment_id: allotmentId, series_id: seriesId } },
        });
        if (error) throw new Error(message(error, "Couldn't stop it"));
      },
      onSuccess: refresh,
    }),
  };
}

export type BookingFilters = { equipmentId?: number; featureId?: number; plantingId?: number; from?: string; to?: string };

/** Equipment in use: all of it, or for one item, bed or planting, or within a window. */
export function useBookings(allotmentId: number, filters: BookingFilters = {}, enabled = true) {
  return useQuery({
    queryKey: ["equipment-bookings", allotmentId, filters],
    enabled,
    placeholderData: keepPreviousData,
    queryFn: async (): Promise<Booking[]> =>
      (
        await api.GET("/api/v1/allotments/{allotment_id}/equipment-bookings", {
          params: {
            ...path(allotmentId),
            query: { equipment_id: filters.equipmentId, feature_id: filters.featureId, planting_id: filters.plantingId, from: filters.from, to: filters.to },
          },
        })
      ).data ?? [],
  });
}

/** Where one item is in use, and the stretches when more is booked than you own. */
export function useItemBookings(allotmentId: number, id: number) {
  return useQuery({
    queryKey: ["equipment-bookings", allotmentId, "item", id],
    queryFn: async () =>
      (await api.GET("/api/v1/allotments/{allotment_id}/equipment/{equipment_id}/bookings", { params: one(allotmentId, id) })).data,
  });
}

export function useBookingActions(allotmentId: number) {
  const qc = useQueryClient();
  const refresh = () => void qc.invalidateQueries({ queryKey: ["equipment-bookings", allotmentId] });
  return {
    create: useMutation({
      mutationFn: async ({ equipmentId, body }: { equipmentId: number; body: BookingInput }): Promise<Booking> => {
        const { data, error } = await api.POST("/api/v1/allotments/{allotment_id}/equipment/{equipment_id}/bookings", {
          params: one(allotmentId, equipmentId),
          body,
        });
        if (!data) throw new Error(message(error, "Couldn't put that to use"));
        return data;
      },
      onSuccess: refresh,
    }),
    remove: useMutation({
      mutationFn: async (id: number) => {
        const { error } = await api.DELETE("/api/v1/allotments/{allotment_id}/equipment-bookings/{booking_id}", {
          params: { path: { allotment_id: allotmentId, booking_id: id } },
        });
        if (error) throw new Error(message(error, "Couldn't remove that"));
      },
      onSuccess: refresh,
    }),
  };
}
