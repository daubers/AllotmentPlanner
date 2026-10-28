import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Overview } from "./summary";

export function useOverview(allotmentId: number, days = 120) {
  return useQuery({
    queryKey: ["overview", allotmentId, days],
    queryFn: async (): Promise<Overview | undefined> =>
      (await api.GET("/api/v1/allotments/{allotment_id}/overview", { params: { path: { allotment_id: allotmentId }, query: { days } } })).data,
  });
}
