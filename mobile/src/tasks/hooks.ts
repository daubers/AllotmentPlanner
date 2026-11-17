import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useCallback } from "react";
import { showDialog } from "../ui/dialog";
import { useApp } from "../state/AppProvider";
import {
  commentRequest,
  completeRequest,
  createRequest,
  localComment,
  localJob,
  reopenRequest,
  withStatus,
  type NewComment,
  type NewJob,
  type Task,
  type TaskComment,
} from "./model";

/** The allotment's jobs (open and done), from the server. */
export function useTasks() {
  const { api, allotmentId, session } = useApp();
  return useQuery({
    queryKey: ["tasks", session.serverUrl, allotmentId],
    enabled: allotmentId !== null,
    queryFn: async (): Promise<Task[]> => {
      const { data, error } = await api.GET("/api/v1/allotments/{allotment_id}/tasks", {
        params: { path: { allotment_id: allotmentId as number }, query: { open: true } },
      });
      if (error || !data) throw new Error("Couldn't load your jobs");
      return data;
    },
  });
}

/** Tick a job off (or put it back): shown at once, sent when there is signal. */
export function useTick() {
  const { queue, allotmentId, session } = useApp();
  const client = useQueryClient();
  return useCallback(
    async (taskId: number, done: boolean) => {
      if (allotmentId === null || taskId < 0) return; // a job not yet sent has no server id to tick
      client.setQueryData(["tasks", session.serverUrl, allotmentId], (old: Task[] | undefined) =>
        old ? withStatus(old, taskId, done ? "done" : "todo") : old,
      );
      await queue.enqueue("request", done ? completeRequest(allotmentId, taskId) : reopenRequest(allotmentId, taskId));
      void queue.run().then(() => client.invalidateQueries({ queryKey: ["tasks", session.serverUrl, allotmentId] }));
    },
    [queue, allotmentId, session.serverUrl, client],
  );
}

/** Add a job: it appears in the list at once and is sent when there is signal. */
export function useAddJob() {
  const { queue, allotmentId, session } = useApp();
  const client = useQueryClient();
  return useCallback(
    async (job: NewJob) => {
      if (allotmentId === null) return;
      client.setQueryData(["tasks", session.serverUrl, allotmentId], (old: Task[] | undefined) => [...(old ?? []), localJob(job)]);
      await queue.enqueue("request", createRequest(allotmentId, job));
      void queue.run().then(() => client.invalidateQueries({ queryKey: ["tasks", session.serverUrl, allotmentId] }));
    },
    [queue, allotmentId, session.serverUrl, client],
  );
}

/** Whether the chosen allotment can be changed (anyone but a viewer). Shares the home screen's cache. */
export function useCanEdit(): boolean {
  const { api, allotmentId, session } = useApp();
  const allotments = useQuery({
    queryKey: ["allotments", session.serverUrl],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/allotments");
      if (error || !data) throw new Error("Couldn't load your allotments");
      return data;
    },
  });
  const current = allotments.data?.find((a) => a.id === allotmentId);
  return current ? current.role !== "viewer" : false;
}

/**
 * Tick a job off (or put it back). Finishing one asks whether to add photos, as many as wanted, which go to the
 * camera screen already linked to the job. `leave` is for the job's own screen: it closes once the question is answered.
 */
export function useDoneFlow() {
  const tick = useTick();
  const router = useRouter();
  return useCallback(
    async (taskId: number, title: string, done: boolean, opts?: { leave?: boolean }) => {
      await tick(taskId, done);
      if (!done) return;
      const photos = { pathname: "/photo" as const, params: { taskId: String(taskId) } };
      showDialog({
        title: "Add photos?",
        message: `Photograph "${title}" while you're there. You can take as many as you like.`,
        actions: [
          { label: "Add photos", kind: "primary", onPress: () => (opts?.leave ? router.replace(photos) : router.push(photos)) },
          { label: "Not now", kind: "secondary", onPress: () => opts?.leave && router.back() },
        ],
        onDismiss: () => opts?.leave && router.back(),
      });
    },
    [tick, router],
  );
}

/** A job's comments, oldest first. */
export function useTaskComments(taskId: number) {
  const { api, allotmentId, session } = useApp();
  return useQuery({
    queryKey: ["task-comments", session.serverUrl, allotmentId, taskId],
    enabled: allotmentId !== null && taskId > 0,
    queryFn: async (): Promise<TaskComment[]> => {
      const { data, error } = await api.GET("/api/v1/allotments/{allotment_id}/tasks/{task_id}/comments", {
        params: { path: { allotment_id: allotmentId as number, task_id: taskId } },
      });
      if (error || !data) throw new Error("Couldn't load the comments");
      return data;
    },
  });
}

/** Add a comment: it shows at once (and moves the job if it sets a status) and is sent when there is signal. */
export function useAddComment(taskId: number) {
  const { queue, allotmentId, session } = useApp();
  const client = useQueryClient();
  return useCallback(
    async (comment: NewComment) => {
      if (allotmentId === null || taskId < 0) return;
      const commentsKey = ["task-comments", session.serverUrl, allotmentId, taskId];
      const tasksKey = ["tasks", session.serverUrl, allotmentId];
      client.setQueryData(commentsKey, (old: TaskComment[] | undefined) => [...(old ?? []), localComment(taskId, comment, "You")]);
      if (comment.status) client.setQueryData(tasksKey, (old: Task[] | undefined) => (old ? withStatus(old, taskId, comment.status!) : old));
      await queue.enqueue("request", commentRequest(allotmentId, taskId, comment));
      void queue.run().then(() => {
        void client.invalidateQueries({ queryKey: commentsKey });
        void client.invalidateQueries({ queryKey: tasksKey });
      });
    },
    [queue, allotmentId, session.serverUrl, client, taskId],
  );
}
