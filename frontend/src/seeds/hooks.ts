import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components } from "../api/schema";
import type { Activity, StockLevel } from "./calendar";

export type Packet = components["schemas"]["Packet"];
export type PacketInput = components["schemas"]["PacketIn"];
export type PacketPatch = components["schemas"]["PacketPatch"];

export type PacketFilters = {
  q?: string;
  stock?: StockLevel;
  month?: number;
  activity?: "sow" | Activity;
  status?: "draft" | "active";
};
export type Scan = components["schemas"]["PacketScan"];

const path = (allotmentId: number) => ({ path: { allotment_id: allotmentId } });
const packetPath = (allotmentId: number, id: number) => ({ path: { allotment_id: allotmentId, packet_id: id } });

export function usePackets(allotmentId: number, filters: PacketFilters = {}) {
  return useQuery({
    queryKey: ["packets", allotmentId, filters],
    queryFn: async (): Promise<Packet[]> =>
      (
        await api.GET("/api/v1/allotments/{allotment_id}/packets", {
          params: { ...path(allotmentId), query: { ...filters, q: filters.q?.trim() || undefined } },
        })
      ).data ?? [],
    placeholderData: keepPreviousData,
  });
}

export function usePacket(allotmentId: number, id: number) {
  return useQuery({
    queryKey: ["packet", allotmentId, id],
    queryFn: async (): Promise<Packet | undefined> =>
      (await api.GET("/api/v1/allotments/{allotment_id}/packets/{packet_id}", { params: packetPath(allotmentId, id) })).data,
    // Photos are processed in the background; keep looking until their thumbnails exist.
    refetchInterval: (q) => (q.state.data?.photos?.some((m) => m.status === "pending") ? 2000 : false),
  });
}

const message = (error: unknown, fallback: string) => (error as { message?: string } | undefined)?.message ?? fallback;

export function usePacketActions(allotmentId: number) {
  const qc = useQueryClient();
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["packets", allotmentId] });
    void qc.invalidateQueries({ queryKey: ["packet", allotmentId] });
  };
  return {
    refresh,
    create: useMutation({
      mutationFn: async (body: PacketInput): Promise<Packet> => {
        const { data, error } = await api.POST("/api/v1/allotments/{allotment_id}/packets", { params: path(allotmentId), body });
        if (!data) throw new Error(message(error, "Couldn't add the packet"));
        return data;
      },
      onSuccess: refresh,
    }),
    patch: useMutation({
      mutationFn: async ({ id, ...body }: PacketPatch & { id: number }): Promise<Packet> => {
        const { data, error } = await api.PATCH("/api/v1/allotments/{allotment_id}/packets/{packet_id}", {
          params: packetPath(allotmentId, id),
          body,
        });
        if (!data) throw new Error(message(error, "Couldn't save the packet"));
        return data;
      },
      onSuccess: refresh,
    }),
    remove: useMutation({
      mutationFn: async (id: number) => {
        const { error } = await api.DELETE("/api/v1/allotments/{allotment_id}/packets/{packet_id}", { params: packetPath(allotmentId, id) });
        if (error) throw new Error(message(error, "Couldn't delete the packet"));
      },
      onSuccess: refresh,
    }),
  };
}

/** Packet photos being read. Polls while any is still waiting or running. */
export function useScans(allotmentId: number) {
  return useQuery({
    queryKey: ["scans", allotmentId],
    queryFn: async (): Promise<Scan[]> =>
      (await api.GET("/api/v1/allotments/{allotment_id}/packet-scans", { params: path(allotmentId) })).data ?? [],
    refetchInterval: (q) => (q.state.data?.some((s) => s.status === "queued" || s.status === "running") ? 3000 : false),
  });
}

export function useScanActions(allotmentId: number) {
  const qc = useQueryClient();
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["scans", allotmentId] });
    void qc.invalidateQueries({ queryKey: ["packets", allotmentId] });
  };
  return {
    start: useMutation({
      mutationFn: async (mediaId: number): Promise<Scan> => {
        const { data, error } = await api.POST("/api/v1/allotments/{allotment_id}/packet-scans", {
          params: path(allotmentId),
          body: { media_id: mediaId },
        });
        if (!data) throw new Error(message(error, "Couldn't start reading that photo"));
        return data;
      },
      onSuccess: refresh,
    }),
    retry: useMutation({
      mutationFn: async (scanId: number): Promise<Scan> => {
        const { data, error } = await api.POST("/api/v1/allotments/{allotment_id}/packet-scans/{scan_id}/retry", {
          params: { path: { allotment_id: allotmentId, scan_id: scanId } },
        });
        if (!data) throw new Error(message(error, "Couldn't try again"));
        return data;
      },
      onSuccess: refresh,
    }),
  };
}

/** Which fields the reader could not find, in the words the form uses. */
export const FIELD_OF_MISSING: Record<string, string> = {
  name: "name",
  supplier: "supplier",
  seeds_in_packet: "seeds_in_packet",
  sow_depth_mm: "sow_depth_mm",
  best_before_year: "best_before_year",
  germinate_days: "germinate_days_min",
  calendar: "calendar",
};
