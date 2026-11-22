import { useRouter } from "expo-router";
import React, { useState } from "react";
import { Pressable, View } from "react-native";
import { useCanEdit, useTasks } from "../../src/tasks/hooks";
import { localDate } from "../../src/tasks/model";
import { Banner, Button, Card, Field, Screen, Section, T } from "../../src/ui/kit";
import { space } from "../../src/ui/theme";
import { useVisitActions } from "../../src/visits/hooks";
import { combineLocalDateTime } from "../../src/visits/model";

export default function NewVisit() {
  const router = useRouter();
  const canEdit = useCanEdit();
  const tasks = useTasks();
  const actions = useVisitActions();
  const [title, setTitle] = useState("");
  const [date, setDate] = useState(localDate());
  const [time, setTime] = useState("09:00");
  const [duration, setDuration] = useState("120");
  const [notes, setNotes] = useState("");
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const open = (tasks.data ?? []).filter((t) => t.status !== "done");

  function toggle(id: number) {
    setPicked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function save() {
    setError(null);
    const starts_at = combineLocalDateTime(date, time);
    if (!starts_at) {
      setError("That date or time doesn't look right.");
      return;
    }
    setBusy(true);
    try {
      await actions.create.mutateAsync({
        title,
        starts_at,
        duration_minutes: Number(duration) || 120,
        notes,
        task_ids: [...picked],
      });
      router.back();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const ready = title.trim().length > 0 && date.length > 0;
  return (
    <Screen title="Plan a visit" subtitle="It shows in your list once saved; this needs a connection.">
      {!canEdit ? <Banner tone="warn" text="You can look at this allotment but not change it." /> : null}
      <Field label="What's the visit for?" value={title} onChangeText={setTitle} maxLength={200} autoFocus returnKeyType="next" />
      <View style={{ flexDirection: "row", gap: space.sm }}>
        <View style={{ flex: 1 }}>
          <Field label="Date" value={date} onChangeText={setDate} placeholder="YYYY-MM-DD" />
        </View>
        <View style={{ flex: 1 }}>
          <Field label="Time" value={time} onChangeText={setTime} placeholder="HH:MM" />
        </View>
        <View style={{ flex: 1 }}>
          <Field label="Minutes" value={duration} onChangeText={setDuration} keyboardType="number-pad" />
        </View>
      </View>
      <Field label="Notes" value={notes} onChangeText={setNotes} maxLength={5000} multiline large={false} />
      <Section title="Jobs to bring" right={<T kind="caption" muted>{picked.size}</T>}>
        {open.length > 0 ? (
          <Card>
            {open.map((t, i) => (
              <Pressable
                key={t.id}
                onPress={() => toggle(t.id!)}
                accessibilityRole="checkbox"
                accessibilityState={{ checked: picked.has(t.id!) }}
                style={{ flexDirection: "row", alignItems: "center", gap: space.sm, paddingVertical: space.sm, paddingHorizontal: space.md, borderTopWidth: i === 0 ? 0 : 1, borderTopColor: "transparent" }}
              >
                <T kind="body" style={{ flex: 1 }}>{t.title}</T>
                <T kind="body" tone={picked.has(t.id!) ? "ok" : "neutral"}>{picked.has(t.id!) ? "✓" : ""}</T>
              </Pressable>
            ))}
          </Card>
        ) : (
          <T muted>{tasks.isLoading ? "Loading jobs…" : "No open jobs to pick from."}</T>
        )}
      </Section>
      {error ? <Banner tone="danger" text={error} /> : null}
      <Button label="Plan visit" onPress={() => void save()} busy={busy} disabled={!canEdit || !ready} />
    </Screen>
  );
}
