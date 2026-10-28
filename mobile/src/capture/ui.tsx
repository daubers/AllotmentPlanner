import React from "react";
import { Pressable, View } from "react-native";
import { SECTORS, verdict, type Summary } from "./coaching";
import type { UploadProgress } from "./sessionUploads";
import type { QueueState } from "../queue/queue";
import { Banner, Button, Card, ProgressBar, Screen, Section, T, type Tone } from "../ui/kit";
import { radius, space, usePalette } from "../ui/theme";

export function Hud({ label, value, tone }: { label: string; value: string; tone: Tone }) {
  const p = usePalette();
  const dot = tone === "ok" ? "#4ade80" : tone === "warn" ? "#fbbf24" : tone === "danger" ? "#f87171" : "#9ca3af";
  return (
    <View
      accessibilityLabel={`${label} ${value}`}
      style={{ flex: 1, backgroundColor: p.overlay, borderRadius: radius.md, paddingVertical: 8, paddingHorizontal: 10, gap: 2 }}
    >
      <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
        <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: dot }} />
        <T kind="caption" style={{ color: "#d1d5db" }}>
          {label}
        </T>
      </View>
      <T kind="label" style={{ color: "#fff" }}>
        {value}
      </T>
    </View>
  );
}

export function Pill({ label, onPress, disabled }: { label: string; onPress: () => void; disabled?: boolean }) {
  const p = usePalette();
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={label}
      style={{ minHeight: 48, minWidth: 80, paddingHorizontal: space.lg, borderRadius: radius.pill, backgroundColor: p.overlay, alignItems: "center", justifyContent: "center", opacity: disabled ? 0.4 : 1 }}
    >
      <T kind="label" style={{ color: "#fff", fontSize: 15 }}>
        {label}
      </T>
    </Pressable>
  );
}

export function Stat({ value, label }: { value: string; label: string }) {
  return (
    <View style={{ flex: 1 }}>
      <Card style={{ alignItems: "center", paddingVertical: space.md, gap: 0 }}>
        <T kind="heading" style={{ fontSize: 22 }}>
          {value}
        </T>
        <T kind="caption" muted>
          {label}
        </T>
      </Card>
    </View>
  );
}

export function CaptureSummary({
  summary,
  uploads,
  queueState,
  mapMessage,
  minPhotos,
  onBuild,
  onKeepGoing,
  onNewWalk,
  onDone,
  onReview,
}: {
  summary: Summary;
  uploads: UploadProgress;
  queueState: QueueState;
  mapMessage: string | null;
  minPhotos: number;
  onBuild: () => void;
  onKeepGoing: () => void;
  onNewWalk: () => void;
  onDone: () => void;
  onReview: () => void;
}) {
  const notes = verdict(summary);
  const good = notes.length === 1 && notes[0].includes("a good set");
  const ready = uploads.waiting === 0 && uploads.failed === 0 && summary.photos >= minPhotos;
  const uploaded = uploads.total - uploads.waiting - uploads.failed;
  return (
    <Screen
      title="Walk finished"
      back={false}
      footer={
        <>
          <Button label="Build a map from this walk" disabled={!ready} onPress={onBuild} />
          {!ready && summary.photos >= minPhotos && uploads.failed === 0 ? (
            <T kind="caption" muted style={{ textAlign: "center" }}>
              Available once every photo has been sent.
            </T>
          ) : null}
          <View style={{ flexDirection: "row", gap: space.sm }}>
            <View style={{ flex: 1 }}>
              <Button label="Add more" kind="secondary" small onPress={onKeepGoing} />
            </View>
            <View style={{ flex: 1 }}>
              <Button label="New walk" kind="secondary" small onPress={onNewWalk} />
            </View>
            <View style={{ flex: 1 }}>
              <Button label="Done" kind="secondary" small onPress={onDone} />
            </View>
          </View>
        </>
      }
    >
      <View style={{ flexDirection: "row", gap: space.sm }}>
        <Stat value={String(summary.photos)} label="photos" />
        <Stat value={`${Math.round(summary.walkedM)} m`} label="walked" />
        <Stat value={`${summary.sectors}/${SECTORS}`} label="directions" />
      </View>
      <Card tone={good ? "ok" : "warn"}>
        <T kind="heading" tone={good ? "ok" : "warn"}>
          {good ? "A good set" : "Worth a look before you build"}
        </T>
        {notes.map((note) => (
          <T key={note}>{note}</T>
        ))}
      </Card>
      <Section title="Upload">
        <Card>
          <T kind="heading">{uploads.waiting === 0 && uploads.failed === 0 ? "All photos are on the server" : `${uploaded} of ${uploads.total} sent`}</T>
          <ProgressBar value={uploaded} total={Math.max(uploads.total, 1)} />
          {queueState.active ? (
            <T kind="caption" muted>
              Sending the current photo: {Math.round(queueState.active.progress * 100)}%
            </T>
          ) : null}
          {uploads.failed ? <Banner tone="danger" text={`${uploads.failed} couldn't be sent`} action="Review" onAction={onReview} /> : null}
        </Card>
      </Section>
      {mapMessage ? <Banner tone={mapMessage.startsWith("Building") ? "ok" : "warn"} text={mapMessage} /> : null}
    </Screen>
  );
}
