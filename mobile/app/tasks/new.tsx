import * as Location from "expo-location";
import { useRouter } from "expo-router";
import React, { useState } from "react";
import { View } from "react-native";
import { useBeds } from "../../src/beds/hooks";
import { daysFrom, type NewJob } from "../../src/tasks/model";
import { useAddJob, useCanEdit } from "../../src/tasks/hooks";
import { Banner, Button, Card, Field, Row, Screen, Section, Segmented, T } from "../../src/ui/kit";
import { space } from "../../src/ui/theme";

type When = "none" | "today" | "tomorrow" | "week";
type Where = "anywhere" | "here" | "bed";

export default function NewJob() {
  const router = useRouter();
  const canEdit = useCanEdit();
  const beds = useBeds();
  const add = useAddJob();
  const [title, setTitle] = useState("");
  const [when, setWhen] = useState<When>("today");
  const [priority, setPriority] = useState<"normal" | "high">("normal");
  const [where, setWhere] = useState<Where>("anywhere");
  const [bedId, setBedId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    setError(null);
    const job: NewJob = {
      title,
      priority,
      due_date: when === "none" ? null : daysFrom(when === "today" ? 0 : when === "tomorrow" ? 1 : 7),
    };
    setBusy(true);
    try {
      if (where === "bed") job.feature_id = bedId;
      if (where === "here") {
        const { granted } = await Location.requestForegroundPermissionsAsync();
        if (!granted) throw new Error("Allow location to pin the job where you are, or choose Anywhere.");
        const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.High });
        job.location = { lat: pos.coords.latitude, lng: pos.coords.longitude };
      }
      await add(job);
      router.back();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const ready = title.trim().length > 0 && (where !== "bed" || bedId !== null);
  return (
    <Screen title="Add a job" subtitle="It shows in your list straight away and is sent when there is signal.">
      {!canEdit ? <Banner tone="warn" text="You can look at this allotment but not change it." /> : null}
      <Field label="What needs doing?" value={title} onChangeText={setTitle} maxLength={200} autoFocus returnKeyType="done" />
      <View style={{ gap: space.xs }}>
        <T kind="label">When</T>
        <Segmented<When>
          value={when}
          onChange={setWhen}
          options={[
            { value: "today", label: "Today" },
            { value: "tomorrow", label: "Tomorrow" },
            { value: "week", label: "Next week" },
            { value: "none", label: "No date" },
          ]}
        />
      </View>
      <View style={{ gap: space.xs }}>
        <T kind="label">Priority</T>
        <Segmented<"normal" | "high"> value={priority} onChange={setPriority} options={[{ value: "normal", label: "Normal" }, { value: "high", label: "High" }]} />
      </View>
      <View style={{ gap: space.xs }}>
        <T kind="label">Where</T>
        <Segmented<Where>
          value={where}
          onChange={setWhere}
          options={[
            { value: "anywhere", label: "Anywhere" },
            { value: "here", label: "Here" },
            { value: "bed", label: "A bed" },
          ]}
        />
        {where === "here" ? <T kind="caption" muted>Pins the job to where you are standing now.</T> : null}
      </View>
      {where === "bed" ? (
        <Section title="Which bed?">
          {beds.data && beds.data.length > 0 ? (
            <Card>
              {beds.data.map((b, i) => (
                <Row key={b.id} first={i === 0} title={b.name} value={b.id === bedId ? "Chosen" : undefined} valueTone="ok" onPress={() => setBedId(b.id)} />
              ))}
            </Card>
          ) : (
            <T muted>{beds.isLoading ? "Loading beds…" : "No beds drawn yet."}</T>
          )}
        </Section>
      ) : null}
      {error ? <Banner tone="danger" text={error} /> : null}
      <Button label="Add job" onPress={() => void save()} busy={busy} disabled={!canEdit || !ready} />
    </Screen>
  );
}
