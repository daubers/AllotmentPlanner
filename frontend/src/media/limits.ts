import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

/** The server's largest accepted upload in bytes (undefined until loaded). */
export function useUploadLimit(): number | undefined {
  return useQuery({
    queryKey: ["limits"],
    queryFn: async () => (await api.GET("/api/v1/limits")).data?.max_upload_bytes,
    staleTime: Infinity,
  }).data;
}
