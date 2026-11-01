import { useInfiniteQuery, useQuery, type InfiniteData } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components, paths } from "../api/schema";

export type Workers = components["schemas"]["Workers"];
export type Worker = components["schemas"]["Worker"];
export type SystemInfo = components["schemas"]["System"];
export type Logs = components["schemas"]["Logs"];
export type Jobs = components["schemas"]["Jobs"];
export type Job = components["schemas"]["Job"];
export type LogEntry = components["schemas"]["LogEntry"];
export type LogFilter = { level: string; service: string; q: string; request_id: string; task_id: string };

/** How often the admin page refreshes itself while it is open. */
export const REFRESH_MS = 10_000;

type LogQuery = NonNullable<paths["/api/v1/admin/logs"]["get"]["parameters"]["query"]>;
const nonEmpty = (filter: LogFilter) => Object.fromEntries(Object.entries(filter).filter(([, v]) => v !== "")) as LogQuery;

export function useAdminWorkers() {
  return useQuery({
    queryKey: ["admin", "workers"],
    refetchInterval: REFRESH_MS,
    queryFn: async () => (await api.GET("/api/v1/admin/workers")).data,
  });
}

export function useAdminSystem() {
  return useQuery({
    queryKey: ["admin", "system"],
    refetchInterval: REFRESH_MS,
    queryFn: async () => (await api.GET("/api/v1/admin/system")).data,
  });
}

export function useAdminJobs() {
  return useQuery({
    queryKey: ["admin", "jobs"],
    refetchInterval: REFRESH_MS,
    queryFn: async () => (await api.GET("/api/v1/admin/jobs")).data,
  });
}

/** Stored log lines, newest first; "load older" fetches the next page. `live` keeps the first page fresh. */
export function useAdminLogs(filter: LogFilter, live: boolean) {
  return useInfiniteQuery<Logs | undefined, Error, InfiniteData<Logs | undefined>, unknown[], number | undefined>({
    queryKey: ["admin", "logs", filter],
    refetchInterval: live ? REFRESH_MS : false,
    initialPageParam: undefined as number | undefined,
    getNextPageParam: (last) => last?.next_before ?? undefined,
    queryFn: async ({ pageParam }): Promise<Logs | undefined> =>
      (await api.GET("/api/v1/admin/logs", { params: { query: { ...nonEmpty(filter), ...(pageParam ? { before_id: pageParam } : {}), limit: 100 } } })).data,
  });
}
