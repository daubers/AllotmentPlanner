import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components } from "../api/schema";
import type { Activity, StockLevel } from "./calendar";

export type Packet = components["schemas"]["Packet"];
export type PacketInput = components["schemas"]["PacketIn"];
export type PacketPatch = components["schemas"]["PacketPatch"];

export type PacketFilters = { q?: string; stock?: StockLevel; month?: number; activity?: "sow" | Activity };

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
