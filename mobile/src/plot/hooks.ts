import { useQuery } from "@tanstack/react-query";
import { useApp } from "../state/AppProvider";
import { shapesOf, type PlotShape } from "./shapes";

/** Everything drawn on the allotment's map, as shapes ready to sketch. */
export function usePlotShapes() {
  const { api, allotmentId, session } = useApp();
  return useQuery({
    queryKey: ["plot-shapes", session.serverUrl, allotmentId],
    enabled: allotmentId !== null,
    queryFn: async (): Promise<PlotShape[]> => {
      const { data, error } = await api.GET("/api/v1/allotments/{allotment_id}/features", {
        params: { path: { allotment_id: allotmentId as number } },
      });
      if (error || !data) throw new Error("Couldn't load the map");
      return shapesOf((data as any).features);
    },
  });
}
