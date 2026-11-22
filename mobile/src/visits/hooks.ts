import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { File, Paths } from "expo-file-system";
import * as Sharing from "expo-sharing";
import { useApp } from "../state/AppProvider";
import type { Session } from "../auth/session";
import type { components } from "../api/schema";

export type Visit = components["schemas"]["Visit"];
export type CalendarToken = components["schemas"]["CalendarToken"];

/** The allotment's visits, soonest first. Online-only: unlike jobs, there is no offline queue yet. */
export function useVisits() {
  const { api, allotmentId, session } = useApp();
  return useQuery({
    queryKey: ["visits", session.serverUrl, allotmentId],
    enabled: allotmentId !== null,
    queryFn: async (): Promise<Visit[]> => {
      const { data, error } = await api.GET("/api/v1/allotments/{allotment_id}/visits", {
        params: { path: { allotment_id: allotmentId as number } },
      });
      if (error || !data) throw new Error("Couldn't load your visits");
      return data;
    },
  });
}

export function useVisit(visitId: number) {
  const { api, allotmentId, session } = useApp();
  return useQuery({
    queryKey: ["visit", session.serverUrl, allotmentId, visitId],
    enabled: allotmentId !== null,
    queryFn: async (): Promise<Visit> => {
      const { data, error } = await api.GET("/api/v1/allotments/{allotment_id}/visits/{visit_id}", {
        params: { path: { allotment_id: allotmentId as number, visit_id: visitId } },
      });
      if (error || !data) throw new Error("Couldn't load that visit");
      return data;
    },
  });
}

export type NewVisit = {
  title: string;
  starts_at: string;
  duration_minutes?: number;
  notes?: string;
  task_ids?: number[];
};

export function useVisitActions() {
  const { api, allotmentId, session } = useApp();
  const client = useQueryClient();
  const refresh = () => void client.invalidateQueries({ queryKey: ["visits", session.serverUrl, allotmentId] });
  return {
    create: useMutation({
      mutationFn: async (visit: NewVisit): Promise<Visit> => {
        const { data, error } = await api.POST("/api/v1/allotments/{allotment_id}/visits", {
          params: { path: { allotment_id: allotmentId as number } },
          body: visit,
        });
        if (error || !data) throw new Error("Couldn't plan the visit");
        return data;
      },
      onSuccess: refresh,
    }),
    remove: useMutation({
      mutationFn: async (visitId: number) => {
        const { error } = await api.DELETE("/api/v1/allotments/{allotment_id}/visits/{visit_id}", {
          params: { path: { allotment_id: allotmentId as number, visit_id: visitId } },
        });
        if (error) throw new Error("Couldn't delete the visit");
      },
      onSuccess: refresh,
    }),
  };
}

/** Download the visit's .ics and hand it to the system share sheet, which lets the person open it
 *  in any calendar app. The endpoint needs a login, so this fetches it itself rather than sharing
 *  the URL directly. */
export async function shareVisitIcs(session: Session, allotmentId: number, visit: Visit): Promise<void> {
  const header = await session.authHeader();
  const resp = await fetch(
    `${session.serverUrl}/api/v1/allotments/${allotmentId}/visits/${visit.id}/calendar.ics`,
    { headers: header ? { Authorization: header } : {} },
  );
  if (!resp.ok) throw new Error("Couldn't download the calendar file");
  const body = await resp.text();
  const file = new File(Paths.cache, `visit-${visit.id}.ics`);
  file.create({ overwrite: true });
  await file.write(body);
  if (!(await Sharing.isAvailableAsync())) throw new Error("Sharing isn't available on this device");
  await Sharing.shareAsync(file.uri, { mimeType: "text/calendar" });
}

/** The feed subscribe URL, if one exists for this allotment. */
export function useCalendarFeed() {
  const { api, allotmentId, session } = useApp();
  return useQuery({
    queryKey: ["calendar-token", session.serverUrl, allotmentId],
    enabled: allotmentId !== null,
    queryFn: async (): Promise<CalendarToken> => {
      const { data, error } = await api.GET("/api/v1/allotments/{allotment_id}/visits/calendar-token", {
        params: { path: { allotment_id: allotmentId as number } },
      });
      if (error || !data) throw new Error("Couldn't load the calendar feed");
      return data;
    },
  });
}
