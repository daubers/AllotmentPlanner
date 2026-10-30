import { useLocalSearchParams, useRouter } from "expo-router";
import React, { useEffect, useState } from "react";
import { View } from "react-native";
import SightingPhoto from "../../src/found/SightingPhoto";
import { useFound, useFoundActions } from "../../src/found/hooks";
import { confidenceWord, KINDS, photosOf, seenIn } from "../../src/found/model";
import { Banner, Button, Card, Chip, Field, Loading, Screen, Section, T } from "../../src/ui/kit";
import { space } from "../../src/ui/theme";

export default function FoundItem() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const found = useFound();
  const actions = useFoundActions();
  const s = found.data?.find((x) => x.id === Number(id));
  const [name, setName] = useState("");
  useEffect(() => setName(s?.name ?? ""), [s?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const problem = actions.edit.error ?? actions.accept.error ?? actions.dismiss.error;

  if (found.isLoading) return <Screen title="Found item"><Loading /></Screen>;
  if (!s) {
    // Added or dismissed (here or on the web), or it never existed.
    return (
      <Screen title="Found item">
        <Banner tone="ok" text="This one has been dealt with." action="Back to the list" onAction={() => router.replace("/found")} />
      </Screen>
    );
  }
  const photos = photosOf(s);
  const done = () => router.replace("/found");
  const rename = () => name.trim() !== (s.name ?? "") && actions.edit.mutate({ id: s.id!, name: name.trim() });

  return (
    <Screen title={s.name || `Unnamed ${s.kind}`} subtitle={`${confidenceWord(s.confidence)} · ${seenIn(s)}`}>
      {problem ? <Banner tone="danger" text={(problem as Error).message} /> : null}
      {photos.length === 0 ? <T muted>No photo was kept for this one: it was found before photos were saved, or only in a video.</T> : null}
      {photos.map((x, i) => (
        <SightingPhoto key={`${x.media_id}-${i}`} sighting={x} full label={`${s.name || s.kind} outlined in photo ${i + 1}`} />
      ))}
      <Field label="Name" value={name} onChangeText={setName} onBlur={rename} onSubmitEditing={rename} returnKeyType="done" />
      <Section title="What is it?">
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.sm }}>
          {KINDS.map((k) => (
            <Button key={k} label={k} small kind={s.kind === k ? "primary" : "secondary"} onPress={() => actions.edit.mutate({ id: s.id!, kind: k })} />
          ))}
        </View>
      </Section>
      <Card>
        <Button label="Add to the map" busy={actions.accept.isPending} onPress={() => actions.accept.mutateAsync([s.id!]).then(done)} />
        <Button label="Dismiss" kind="secondary" busy={actions.dismiss.isPending} onPress={() => actions.dismiss.mutateAsync([s.id!]).then(done)} />
      </Card>
    </Screen>
  );
}
