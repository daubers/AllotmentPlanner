import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, getSession } from "../api/client";
import type { components } from "../api/schema";

export type Visit = components["schemas"]["Visit"];
export type CalendarToken = components["schemas"]["CalendarToken"];

const path = (allotmentId: number) => ({ path: { allotment_id: allotmentId } });
const visitPath = (allotmentId: number, visitId: number) => ({
  path: { allotment_id: allotmentId, visit_id: visitId },
});
const failure = (error: unknown, fallback: string) =>
  (error as { message?: string } | undefined)?.message ?? fallback;

export function useVisits(allotmentId: number) {
  return useQuery({
    queryKey: ["visits", allotmentId],
    queryFn: async (): Promise<Visit[]> =>
      (await api.GET("/api/v1/allotments/{allotment_id}/visits", { params: path(allotmentId) })).data ?? [],
  });
}

export function useVisitActions(allotmentId: number) {
  const qc = useQueryClient();
  const refresh = () => void qc.invalidateQueries({ queryKey: ["visits", allotmentId] });
  return {
    create: useMutation({
      mutationFn: async (body: {
        title: string;
        starts_at: string;
        duration_minutes?: number;
        notes?: string;
        task_ids?: number[];
      }): Promise<Visit> => {
        const { data, error } = await api.POST("/api/v1/allotments/{allotment_id}/visits", {
          params: path(allotmentId),
          body,
        });
        if (!data) throw new Error(failure(error, "Could not plan the visit"));
        return data;
      },
      onSuccess: refresh,
    }),
    update: useMutation({
      mutationFn: async ({
        id,
        body,
      }: {
        id: number;
        body: { title?: string; starts_at?: string; duration_minutes?: number; notes?: string };
      }) => {
        const { data, error } = await api.PATCH("/api/v1/allotments/{allotment_id}/visits/{visit_id}", {
          params: visitPath(allotmentId, id),
          body,
        });
        if (!data) throw new Error(failure(error, "Could not save the visit"));
        return data;
      },
      onSuccess: refresh,
    }),
    remove: useMutation({
      mutationFn: async (id: number) => {
        const { error } = await api.DELETE("/api/v1/allotments/{allotment_id}/visits/{visit_id}", {
          params: visitPath(allotmentId, id),
        });
        if (error) throw new Error(failure(error, "Could not delete the visit"));
      },
      onSuccess: refresh,
    }),
    addTasks: useMutation({
      mutationFn: async ({ id, taskIds }: { id: number; taskIds: number[] }) => {
        const { data, error } = await api.POST(
          "/api/v1/allotments/{allotment_id}/visits/{visit_id}/tasks",
          { params: visitPath(allotmentId, id), body: { task_ids: taskIds } },
        );
        if (!data) throw new Error(failure(error, "Could not peg those tasks"));
        return data;
      },
      onSuccess: refresh,
    }),
    removeTask: useMutation({
      mutationFn: async ({ id, taskId }: { id: number; taskId: number }) => {
        const { error } = await api.DELETE(
          "/api/v1/allotments/{allotment_id}/visits/{visit_id}/tasks/{task_id}",
          { params: { path: { allotment_id: allotmentId, visit_id: id, task_id: taskId } } },
        );
        if (error) throw new Error(failure(error, "Could not unpeg that task"));
      },
      onSuccess: refresh,
    }),
  };
}

export function useCalendarToken(allotmentId: number) {
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: ["calendar-token", allotmentId],
    queryFn: async (): Promise<CalendarToken> =>
      (await api.GET("/api/v1/allotments/{allotment_id}/visits/calendar-token", { params: path(allotmentId) })).data ?? { token: null, feed_url: null },
  });
  const refresh = () => void qc.invalidateQueries({ queryKey: ["calendar-token", allotmentId] });
  return {
    ...query,
    rotate: useMutation({
      mutationFn: async (): Promise<CalendarToken> => {
        const { data, error } = await api.POST("/api/v1/allotments/{allotment_id}/visits/calendar-token", {
          params: path(allotmentId),
        });
        if (!data) throw new Error(failure(error, "Could not create the feed"));
        return data;
      },
      onSuccess: refresh,
    }),
    disable: useMutation({
      mutationFn: async () => {
        const { error } = await api.DELETE("/api/v1/allotments/{allotment_id}/visits/calendar-token", {
          params: path(allotmentId),
        });
        if (error) throw new Error(failure(error, "Could not turn off the feed"));
      },
      onSuccess: refresh,
    }),
  };
}

/** Google Calendar's prefilled "create event" link; opens in a new tab, nothing is saved server-side. */
export function googleCalendarUrl(visit: Visit): string {
  const start = new Date(visit.starts_at!);
  const end = new Date(start.getTime() + (visit.duration_minutes ?? 120) * 60_000);
  const stamp = (d: Date) => d.toISOString().replace(/[-:]|\.\d{3}/g, "");
  const params = new URLSearchParams({
    action: "TEMPLATE",
    text: visit.title ?? "",
    dates: `${stamp(start)}/${stamp(end)}`,
    details: visit.notes ?? "",
  });
  return `https://calendar.google.com/calendar/render?${params.toString()}`;
}

/** Download the visit's single-event .ics. The endpoint needs a JWT, so a plain <a href> can't be
 *  used: fetch it with the session token and save the response as a file instead. */
export async function downloadVisitIcs(allotmentId: number, visit: Visit): Promise<void> {
  const session = getSession();
  const resp = await fetch(
    `/api/v1/allotments/${allotmentId}/visits/${visit.id}/calendar.ics`,
    { headers: session ? { Authorization: `Bearer ${session.access_token}` } : {} },
  );
  if (!resp.ok) throw new Error("Could not download the calendar file");
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `visit-${visit.id}.ics`;
  a.click();
  URL.revokeObjectURL(url);
}
