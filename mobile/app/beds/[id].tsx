import { useLocalSearchParams, useRouter } from "expo-router";
import React, { useState } from "react";
import { View } from "react-native";
import BedSketch from "../../src/beds/BedSketch";
import { areaLabel, GROWING, ringOf, STATUS_LABEL, STATUSES } from "../../src/beds/geometry";
import { useBeds, usePlantings, usePlantingStatus } from "../../src/beds/hooks";
import { Banner, Button, Card, Chip, Empty, Loading, Screen, Section, T } from "../../src/ui/kit";
import { space } from "../../src/ui/theme";

const TONE: Record<string, "neutral" | "ok" | "warn" | "danger"> = { sown: "warn", growing: "ok", harvesting: "ok", finished: "neutral", failed: "danger" };

export default function Bed() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const featureId = Number(id);
  const router = useRouter();
  const beds = useBeds();
  const plantings = usePlantings();
  const setStatus = usePlantingStatus();
  const [showDone, setShowDone] = useState(false);
  const [open, setOpen] = useState<number | null>(null);
  const bed = beds.data?.find((b) => b.id === featureId);

  if (beds.isLoading) return <Screen title="Bed"><Loading /></Screen>;
  if (!bed) return <Screen title="Bed"><Banner tone="danger" text="Couldn't find that bed." /></Screen>;

  const mine = (plantings.data ?? []).filter((pl) => pl.feature_id === featureId);
  const shown = showDone ? mine : mine.filter((pl) => GROWING.includes(pl.status ?? ""));
  const label = (pl: (typeof mine)[number]) => (pl.packet_name ? (pl.packet_variety ? `${pl.packet_name} (${pl.packet_variety})` : pl.packet_name) : "Unknown seed");

  return (
    <Screen title={bed.name} subtitle="Planting areas are drawn in the web app; here you follow them through the season.">
      <Card>
        <BedSketch ring={bed.ring} regions={shown.map((pl) => ({ id: pl.id!, label: label(pl), ring: ringOf(pl.region), packetId: pl.packet_id, selected: pl.id === open }))} />
      </Card>
      {plantings.isLoading ? <Loading /> : null}
      {plantings.data && shown.length === 0 ? <Empty title="Nothing growing here" body="Plant out a tray, or sow a bed from the web app, and it appears here." /> : null}
      <Section title="In this bed">
        {shown.map((pl) => (
          <Card key={pl.id}>
            <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: space.sm }}>
              <T kind="heading" style={{ flex: 1 }}>{label(pl)}</T>
              <Chip label={STATUS_LABEL[pl.status ?? ""] ?? pl.status ?? ""} tone={TONE[pl.status ?? ""] ?? "neutral"} />
            </View>
            <T kind="caption" muted>
              {areaLabel(pl.area_m2 ?? 0)}
              {pl.count ? ` · ${pl.count}` : ""}
              {pl.method === "transplant" ? " · planted out" : " · sown here"}
              {pl.sown_on ? ` · sown ${pl.sown_on}` : ""}
            </T>
            {open === pl.id ? (
              <View style={{ gap: space.sm }}>
                <T kind="label">Change its state</T>
                <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.sm }}>
                  {STATUSES.filter((s) => s.value !== pl.status).map((s) => (
                    <Button key={s.value} label={s.label} small kind="secondary" onPress={() => void setStatus(pl.id!, s.value)} />
                  ))}
                </View>
                <Button label="Add a photo" kind="secondary" small onPress={() => router.push(`/photo?plantingId=${pl.id}`)} />
              </View>
            ) : null}
            <Button label={open === pl.id ? "Done" : "Update"} kind="quiet" small onPress={() => setOpen(open === pl.id ? null : pl.id!)} />
          </Card>
        ))}
      </Section>
      <Button label={showDone ? "Hide finished and failed" : "Show finished and failed too"} kind="quiet" small onPress={() => setShowDone(!showDone)} />
    </Screen>
  );
}
