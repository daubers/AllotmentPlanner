import { useRouter } from "expo-router";
import React from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { useBeds } from "../../src/beds/hooks";
import { dueLabel, groupTasks, type Task } from "../../src/tasks/model";
import JobSwitch from "../../src/tasks/JobSwitch";
import { useCanEdit, useDoneFlow, useTasks } from "../../src/tasks/hooks";
import { useApp } from "../../src/state/AppProvider";
import { Banner, Button, Card, Chip, Empty, Loading, Screen, Section, T } from "../../src/ui/kit";
import { space, usePalette } from "../../src/ui/theme";

function Job({ task, place, canEdit, onTick, onOpen }: { task: Task; place?: string; canEdit: boolean; onTick: (done: boolean) => void; onOpen: () => void }) {
  const p = usePalette();
  const done = task.status === "done";
  const late = !done && (dueLabel(task.due_date).includes("late"));
  const detail = [dueLabel(task.due_date), place, task.priority === "high" ? "High priority" : ""].filter(Boolean).join(" · ");
  return (
    <View style={[styles.job, { borderTopColor: p.border }]}>
      <Pressable onPress={onOpen} accessibilityRole="button" accessibilityLabel={`Open job: ${task.title}`} style={{ flex: 1, gap: 2 }}>
        <T kind="body" style={{ fontWeight: "500", textDecorationLine: done ? "line-through" : "none" }} muted={done}>
          {task.title}
        </T>
        {detail ? <T kind="caption" muted tone={late ? "danger" : "neutral"}>{detail}</T> : null}
        {task.id! < 0 ? <T kind="caption" muted>Waiting to send</T> : null}
      </Pressable>
      <JobSwitch title={task.title ?? "job"} done={done} disabled={!canEdit || task.id! < 0} onChange={onTick} />
    </View>
  );
}

export default function Jobs() {
  const router = useRouter();
  const { allotmentId } = useApp();
  const tasks = useTasks();
  const beds = useBeds();
  const finish = useDoneFlow();
  const canEdit = useCanEdit();
  const g = groupTasks(tasks.data ?? []);
  const total = g.overdue.length + g.today.length + g.upcoming.length + g.undated.length;
  const bedName = (id?: number | null) => beds.data?.find((b) => b.id === id)?.name;

  const group = (title: string, list: Task[], tone?: "danger") =>
    list.length > 0 ? (
      <Section title={title} right={tone ? <Chip label={`${list.length}`} tone={tone} /> : <T kind="caption" muted>{list.length}</T>}>
        <Card>
          {list.map((t) => (
            <Job
              key={t.id}
              task={t}
              canEdit={canEdit}
              place={bedName(t.feature_id) ?? (t.location ? "Pinned on the map" : undefined)}
              onTick={(done) => void finish(t.id!, t.title ?? "this job", done)}
              onOpen={() => router.push({ pathname: "/tasks/[id]", params: { id: String(t.id) } })}
            />
          ))}
        </Card>
      </Section>
    ) : null;

  return (
    <Screen title="Jobs" subtitle="What needs doing on the plot. Ticks and new jobs are sent when there is signal.">
      {allotmentId === null ? <Empty title="No allotment chosen" body="Choose one on the home screen." /> : null}
      {tasks.isError ? <Banner tone="danger" text={(tasks.error as Error).message} action="Try again" onAction={() => tasks.refetch()} /> : null}
      {tasks.isLoading ? <Loading /> : null}
      {canEdit ? <Button label="Add a job" onPress={() => router.push("/tasks/new")} /> : <T kind="caption" muted>You can look at the jobs but not change them.</T>}
      {tasks.data && total === 0 ? <Empty title="Nothing to do" body="Enjoy the sunshine. New jobs from the web app or this phone show up here." /> : null}
      {group("Overdue", g.overdue, "danger")}
      {group("Today", g.today)}
      {group("Coming up", g.upcoming)}
      {group("No date", g.undated)}
    </Screen>
  );
}

const styles = StyleSheet.create({
  job: { flexDirection: "row", alignItems: "center", gap: space.md, paddingVertical: space.md, paddingHorizontal: space.md, borderTopWidth: StyleSheet.hairlineWidth },
  box: { width: 28, height: 28, borderRadius: 14, borderWidth: 2, alignItems: "center", justifyContent: "center" },
});
