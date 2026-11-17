import { useLocalSearchParams, useRouter } from "expo-router";
import React from "react";
import { View } from "react-native";
import { useBeds } from "../../src/beds/hooks";
import JobSwitch from "../../src/tasks/JobSwitch";
import TaskComments from "../../src/tasks/TaskComments";
import { useCanEdit, useDoneFlow, useTasks } from "../../src/tasks/hooks";
import { dueLabel } from "../../src/tasks/model";
import { Banner, Button, Card, Chip, Loading, Row, Screen, T } from "../../src/ui/kit";
import { space } from "../../src/ui/theme";
import UploadBanner from "../../src/ui/UploadBanner";

/** One job: what it is, when it is due, where it is, and a switch to mark it done. */
export default function Job() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const taskId = Number(id);
  const router = useRouter();
  const tasks = useTasks();
  const beds = useBeds();
  const finish = useDoneFlow();
  const canEdit = useCanEdit();
  const task = tasks.data?.find((t) => t.id === taskId);

  if (tasks.isLoading) return <Screen title="Job"><Loading /></Screen>;
  if (!task) {
    return (
      <Screen title="Job">
        <Banner tone="warn" text="This job isn't on your list any more. It may be done, or removed on the web." action="All jobs" onAction={() => router.replace("/tasks")} />
      </Screen>
    );
  }

  const done = task.status === "done";
  const due = dueLabel(task.due_date);
  const late = !done && due.includes("late");
  const place = beds.data?.find((b) => b.id === task.feature_id)?.name ?? (task.location ? "Pinned on the map" : "Anywhere");
  const waiting = (task.id ?? 0) < 0;

  return (
    <Screen title={task.title ?? "Job"} subtitle={done ? "Done" : late ? due : undefined}>
      <UploadBanner />
      <Card>
        <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: space.md }}>
          <T kind="heading">{done ? "Done" : "Mark as done"}</T>
          <JobSwitch title={task.title ?? "job"} done={done} disabled={!canEdit || waiting} onChange={(v) => void finish(taskId, task.title ?? "this job", v, { leave: true })} />
        </View>
        {waiting ? <T kind="caption" muted>Waiting to send; you can tick it once it has gone.</T> : null}
        {!canEdit ? <T kind="caption" muted>You can look at this job but not change it.</T> : null}
      </Card>
      <Card>
        <Row first title="Due" value={due || "No date"} valueTone={late ? "danger" : "neutral"} />
        <Row title="Where" value={place} />
        <Row title="Priority" value={task.priority === "high" ? "High" : task.priority === "low" ? "Low" : "Normal"} />
        {task.recurrence ? <Row title="Repeats" value={task.recurrence} /> : null}
      </Card>
      {task.description ? (
        <Card>
          <T kind="heading">Notes</T>
          <T>{task.description}</T>
        </Card>
      ) : null}
      {!waiting ? <TaskComments taskId={taskId} canEdit={canEdit} /> : null}
      {canEdit && !waiting ? <Button label="Add a photo" kind="secondary" onPress={() => router.push({ pathname: "/photo", params: { taskId: String(taskId) } })} /> : null}
    </Screen>
  );
}
