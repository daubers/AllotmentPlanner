import { useRouter } from "expo-router";
import React from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { useBeds } from "../../src/beds/hooks";
import { dueLabel, groupTasks, type Task } from "../../src/tasks/model";
import { useCanEdit, useTasks, useTick } from "../../src/tasks/hooks";
import { useApp } from "../../src/state/AppProvider";
import { Banner, Button, Card, Chip, Empty, Loading, Screen, Section, T } from "../../src/ui/kit";
import { space, usePalette } from "../../src/ui/theme";

function Job({ task, place, canEdit, onTick, onPhoto }: { task: Task; place?: string; canEdit: boolean; onTick: (done: boolean) => void; onPhoto: () => void }) {
  const p = usePalette();
  const done = task.status === "done";
  const late = !done && (dueLabel(task.due_date).includes("late"));
  const detail = [dueLabel(task.due_date), place, task.priority === "high" ? "High priority" : ""].filter(Boolean).join(" · ");
  return (
    <View style={[styles.job, { borderTopColor: p.border }]}>
      <Pressable
        accessibilityRole="checkbox"
        accessibilityState={{ checked: done, disabled: !canEdit || task.id! < 0 }}
        accessibilityLabel={`${done ? "Put back" : "Done"}: ${task.title}`}
        disabled={!canEdit || task.id! < 0}
        onPress={() => onTick(!done)}
        hitSlop={8}
        style={[styles.box, { borderColor: done ? p.accent : p.muted, backgroundColor: done ? p.accent : "transparent" }]}
      >
        {done ? <T kind="heading" style={{ color: p.onAccent, fontSize: 18, lineHeight: 20 }}>✓</T> : null}
      </Pressable>
      <View style={{ flex: 1, gap: 2 }}>
        <T kind="body" style={{ fontWeight: "500", textDecorationLine: done ? "line-through" : "none" }} muted={done}>
          {task.title}
        </T>
        {detail ? <T kind="caption" muted tone={late ? "danger" : "neutral"}>{detail}</T> : null}
        {task.id! < 0 ? <T kind="caption" muted>Waiting to send</T> : null}
      </View>
      {canEdit && task.id! > 0 ? <Button label="Photo" kind="quiet" small onPress={onPhoto} /> : null}
    </View>
  );
}

export default function Jobs() {
  const router = useRouter();
  const { allotmentId } = useApp();
  const tasks = useTasks();
  const beds = useBeds();
  const tick = useTick();
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
              onTick={(done) => void tick(t.id!, done)}
              onPhoto={() => router.push({ pathname: "/photo", params: { taskId: String(t.id) } })}
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
