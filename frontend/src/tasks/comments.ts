import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components } from "../api/schema";

export type TaskComment = components["schemas"]["TaskComment"];
export type NewTaskComment = { body?: string; status?: "todo" | "doing" | "done" | null; progress?: string | null };
export type TaskCommentPatch = { body?: string; progress?: string | null };

const failure = (error: unknown, fallback: string) => (error as { message?: string } | undefined)?.message ?? fallback;
const where = (allotmentId: number, taskId: number) => ({ allotment_id: allotmentId, task_id: taskId });

/** A task's comments, oldest first. */
export function useTaskComments(allotmentId: number, taskId: number) {
  return useQuery({
    queryKey: ["task-comments", allotmentId, taskId],
    queryFn: async (): Promise<TaskComment[]> =>
      (await api.GET("/api/v1/allotments/{allotment_id}/tasks/{task_id}/comments", { params: { path: where(allotmentId, taskId) } })).data ?? [],
  });
}

export function useTaskCommentActions(allotmentId: number, taskId: number) {
  const qc = useQueryClient();
  const refreshComments = () => void qc.invalidateQueries({ queryKey: ["task-comments", allotmentId, taskId] });
  // A comment can move the task, so the lists built from the tasks are refreshed too.
  const refreshTasks = () => {
    void qc.invalidateQueries({ queryKey: ["tasks", allotmentId] });
    void qc.invalidateQueries({ queryKey: ["todo", allotmentId] });
    void qc.invalidateQueries({ queryKey: ["day-lists", allotmentId] });
    void qc.invalidateQueries({ queryKey: ["day-list-sheet", allotmentId] });
  };
  return {
    create: useMutation({
      mutationFn: async (body: NewTaskComment) => {
        const { data, error } = await api.POST("/api/v1/allotments/{allotment_id}/tasks/{task_id}/comments", {
          params: { path: where(allotmentId, taskId) },
          body,
        });
        if (!data) throw new Error(failure(error, "Could not save comment"));
        return data;
      },
      onSuccess: () => {
        refreshComments();
        refreshTasks();
      },
    }),
    update: useMutation({
      mutationFn: async ({ id, body }: { id: number; body: TaskCommentPatch }) => {
        const { data, error } = await api.PATCH("/api/v1/allotments/{allotment_id}/tasks/{task_id}/comments/{comment_id}", {
          params: { path: { ...where(allotmentId, taskId), comment_id: id } },
          body,
        });
        if (!data) throw new Error(failure(error, "Could not save comment"));
        return data;
      },
      onSuccess: refreshComments,
    }),
    remove: useMutation({
      mutationFn: async (id: number) => {
        const { error } = await api.DELETE("/api/v1/allotments/{allotment_id}/tasks/{task_id}/comments/{comment_id}", {
          params: { path: { ...where(allotmentId, taskId), comment_id: id } },
        });
        if (error) throw new Error(failure(error, "Could not delete comment"));
      },
      onSuccess: refreshComments,
    }),
  };
}
