import React, { useState } from "react";
import { View } from "react-native";
import { Button, Card, Chip, Field, Segmented, Section, T } from "../ui/kit";
import { space } from "../ui/theme";
import { useAddComment, useTaskComments } from "./hooks";
import { commentStamp, hasSomethingToSay, type JobStatus } from "./model";

type Choice = "keep" | JobStatus;
const LABEL: Record<JobStatus, string> = { todo: "To do", doing: "In progress", done: "Done" };

/** A job's comment timeline, with a form to add one (optionally moving the job to a new status). */
export default function TaskComments({ taskId, canEdit }: { taskId: number; canEdit: boolean }) {
  const comments = useTaskComments(taskId);
  const add = useAddComment(taskId);
  const [body, setBody] = useState("");
  const [progress, setProgress] = useState("");
  const [status, setStatus] = useState<Choice>("keep");
  const [problem, setProblem] = useState("");

  async function send() {
    const comment = { body, progress, status: status === "keep" ? null : status };
    if (!hasSomethingToSay(comment)) {
      setProblem("Write something, or choose a status or progress");
      return;
    }
    setProblem("");
    setBody("");
    setProgress("");
    setStatus("keep");
    await add(comment);
  }

  return (
    <Section title="Comments">
      {comments.data?.length === 0 ? <T muted>No comments yet.</T> : null}
      {comments.data?.map((c) => (
        <Card key={c.id}>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.sm, alignItems: "center" }}>
            <T kind="label">{commentStamp(c.created_at!)}</T>
            <T kind="caption" muted>{c.author ?? "Someone"}{c.edited ? " (edited)" : ""}</T>
            {c.status ? <Chip label={LABEL[c.status as JobStatus] ?? c.status} tone={c.status === "done" ? "ok" : "neutral"} /> : null}
            {c.progress ? <Chip label={c.progress} /> : null}
          </View>
          {c.body ? <T>{c.body}</T> : null}
        </Card>
      ))}
      {canEdit ? (
        <Card>
          <Field label="Add a comment" value={body} onChangeText={setBody} multiline maxLength={5000} />
          <View style={{ gap: space.xs }}>
            <T kind="label">Status</T>
            <Segmented<Choice>
              value={status}
              onChange={setStatus}
              options={[
                { value: "keep", label: "No change" },
                { value: "doing", label: "In progress" },
                { value: "done", label: "Done" },
              ]}
            />
          </View>
          <Field label="Progress (optional)" value={progress} onChangeText={setProgress} maxLength={80} placeholder="e.g. waiting on seed" />
          {problem ? <T tone="danger">{problem}</T> : null}
          <Button label="Add comment" onPress={() => void send()} />
        </Card>
      ) : null}
    </Section>
  );
}
