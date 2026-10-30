import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useApp } from "../state/AppProvider";
import { applyPatch, type Kind, type Suggestion } from "./model";

const say = (error: unknown, fallback: string) => (error as { message?: string } | undefined)?.message ?? fallback;

/** Objects the photos turned up that are waiting to be added to the map. */
export function useFound() {
  const { api, allotmentId, session } = useApp();
  return useQuery({
    queryKey: ["found", session.serverUrl, allotmentId],
    enabled: allotmentId !== null,
    queryFn: async (): Promise<Suggestion[]> => {
      const { data, error } = await api.GET("/api/v1/allotments/{allotment_id}/suggestions", {
        params: { path: { allotment_id: allotmentId as number }, query: { status: "pending" } },
      });
      if (error || !data) throw new Error("Couldn't load what was found in your photos");
      return data;
    },
  });
}

/** Rename, re-kind, accept or dismiss. These need a connection: each answers with what the server did. */
export function useFoundActions() {
  const { api, allotmentId, session } = useApp();
  const client = useQueryClient();
  const key = ["found", session.serverUrl, allotmentId];
  const path = { path: { allotment_id: allotmentId as number } };
  const refresh = () => {
    void client.invalidateQueries({ queryKey: key });
    void client.invalidateQueries({ queryKey: ["beds"] });
  };
  return {
    edit: useMutation({
      onMutate: async ({ id, ...patch }: { id: number; name?: string; kind?: Kind }) => {
        await client.cancelQueries({ queryKey: key });
        const before = client.getQueryData<Suggestion[]>(key);
        if (before) client.setQueryData(key, applyPatch(before, id, patch));
        return { before };
      },
      onError: (_e, _v, ctx) => {
        if (ctx?.before) client.setQueryData(key, ctx.before);
      },
      mutationFn: async ({ id, ...body }: { id: number; name?: string; kind?: Kind }) => {
        const { data, error } = await api.PATCH("/api/v1/allotments/{allotment_id}/suggestions/{suggestion_id}", {
          params: { path: { allotment_id: allotmentId as number, suggestion_id: id } },
          body,
        });
        if (!data) throw new Error(say(error, "Couldn't save that. Are you online?"));
      },
      onSettled: refresh,
    }),
    accept: useMutation({
      mutationFn: async (ids: number[]) => {
        const { data, error } = await api.POST("/api/v1/allotments/{allotment_id}/suggestions/accept", { params: path, body: { ids } });
        if (!data) throw new Error(say(error, "Couldn't add them to the map. Are you online?"));
      },
      onSuccess: refresh,
    }),
    dismiss: useMutation({
      mutationFn: async (ids: number[]) => {
        const { error, response } = await api.POST("/api/v1/allotments/{allotment_id}/suggestions/dismiss", { params: path, body: { ids } });
        if (!response.ok) throw new Error(say(error, "Couldn't dismiss them. Are you online?"));
      },
      onSuccess: refresh,
    }),
  };
}
