import { useQuery } from "@tanstack/react-query";
import { useApp } from "../state/AppProvider";

export function usePackets(status: "active" | "draft") {
  const { api, allotmentId, session } = useApp();
  return useQuery({
    queryKey: ["packets", session.serverUrl, allotmentId, status],
    enabled: allotmentId !== null,
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/allotments/{allotment_id}/packets", {
        params: { path: { allotment_id: allotmentId as number }, query: { status } },
      });
      if (error || !data) throw new Error("Couldn't load your seeds");
      return data;
    },
  });
}

export function usePacket(id: number) {
  const { api, allotmentId, session } = useApp();
  return useQuery({
    queryKey: ["packet", session.serverUrl, allotmentId, id],
    enabled: allotmentId !== null,
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/allotments/{allotment_id}/packets/{packet_id}", {
        params: { path: { allotment_id: allotmentId as number, packet_id: id } },
      });
      if (error || !data) throw new Error("Couldn't load that packet");
      return data;
    },
  });
}

/** Packet photos being read. Polls while any is still waiting or running. */
export function useScans() {
  const { api, allotmentId, session } = useApp();
  return useQuery({
    queryKey: ["scans", session.serverUrl, allotmentId],
    enabled: allotmentId !== null,
    refetchInterval: (q) => (q.state.data?.some((s) => s.status === "queued" || s.status === "running") ? 4000 : false),
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/allotments/{allotment_id}/packet-scans", {
        params: { path: { allotment_id: allotmentId as number } },
      });
      if (error || !data) throw new Error("Couldn't load your scans");
      return data;
    },
  });
}

/** An absolute address for a media link the server gave as a path. */
export function useMediaUrl() {
  const { session } = useApp();
  return (path?: string | null) => (path ? `${session.serverUrl}${path}` : undefined);
}
