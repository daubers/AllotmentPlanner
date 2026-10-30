import { useRouter } from "expo-router";
import React from "react";
import { Pressable, View } from "react-native";
import SightingPhoto from "../../src/found/SightingPhoto";
import { useFound, useFoundActions } from "../../src/found/hooks";
import { confidenceWord, isLikely, photosOf, seenIn } from "../../src/found/model";
import { Banner, Button, Card, Chip, Empty, Loading, Screen, T } from "../../src/ui/kit";
import { space } from "../../src/ui/theme";


export default function Found() {
  const router = useRouter();
  const found = useFound();
  const actions = useFoundActions();
  const list = found.data ?? [];
  const likely = list.filter(isLikely);
  const problem = actions.accept.error ?? actions.dismiss.error;

  return (
    <Screen title="Found in your photos" subtitle="Check each one against the photo, then add it to your map.">
      {found.isError ? <Banner tone="danger" text={(found.error as Error).message} action="Try again" onAction={() => found.refetch()} /> : null}
      {problem ? <Banner tone="danger" text={(problem as Error).message} /> : null}
      {found.isLoading ? <Loading /> : null}
      {found.data && list.length === 0 ? <Empty title="Nothing to review" body="Build a map from your photos in the web app and what it finds will appear here." /> : null}
      {likely.length > 0 ? (
        <Button
          label={`Add the ${likely.length} likely ${likely.length === 1 ? "one" : "ones"} to the map`}
          busy={actions.accept.isPending}
          onPress={() => actions.accept.mutate(likely.map((s) => s.id!))}
        />
      ) : null}
      {list.map((s) => {
        const first = photosOf(s)[0];
        return (
          <Card key={s.id}>
            <Pressable accessibilityRole="button" accessibilityLabel={`Open ${s.name || s.kind}`} onPress={() => router.push(`/found/${s.id}`)} style={{ gap: space.sm }}>
              {first ? <SightingPhoto sighting={first} label={`${s.name || s.kind} outlined in a photo`} /> : null}
              <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: space.sm }}>
                <View style={{ flex: 1 }}>
                  <T kind="heading">{s.name || `Unnamed ${s.kind}`}</T>
                  <T kind="caption" muted>{s.kind} · {seenIn(s)}</T>
                </View>
                <Chip label={confidenceWord(s.confidence)} tone={isLikely(s) ? "ok" : "warn"} />
              </View>
            </Pressable>
            <View style={{ flexDirection: "row", gap: space.sm }}>
              <View style={{ flex: 1 }}><Button label="Add" small busy={actions.accept.isPending} onPress={() => actions.accept.mutate([s.id!])} /></View>
              <View style={{ flex: 1 }}><Button label="Dismiss" kind="secondary" small busy={actions.dismiss.isPending} onPress={() => actions.dismiss.mutate([s.id!])} /></View>
            </View>
          </Card>
        );
      })}
    </Screen>
  );
}
