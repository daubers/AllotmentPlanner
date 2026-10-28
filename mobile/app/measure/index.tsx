import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import React, { useState } from "react";
import { View } from "react-native";
import { useChecklist } from "../../src/measure/hooks";
import { formatLength, type LengthUnit } from "../../src/measure/units";
import { useApp } from "../../src/state/AppProvider";
import { Banner, Button, Card, Chip, Empty, Loading, ProgressBar, Row, Screen, Section, Segmented, T } from "../../src/ui/kit";
import { space } from "../../src/ui/theme";

const UNITS: { value: LengthUnit; label: string }[] = [
  { value: "m", label: "Metres" },
  { value: "cm", label: "Centimetres" },
  { value: "ft_in", label: "Feet & inches" },
];

export default function Measure() {
  const { api, allotmentId, session } = useApp();
  const router = useRouter();
  const client = useQueryClient();
  const checklist = useChecklist();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const data = checklist.data;

  async function refreshFromMap() {
    if (allotmentId === null) return;
    setBusy(true);
    setMessage(null);
    const { data: next, error } = await api.POST("/api/v1/allotments/{allotment_id}/measurements/sync", {
      params: { path: { allotment_id: allotmentId } },
    });
    setBusy(false);
    if (next) client.setQueryData(["measurements", session.serverUrl, allotmentId], next);
    else setMessage((error as { message?: string } | undefined)?.message ?? "Couldn't update the checklist. Are you online?");
  }

  async function chooseUnit(unit: LengthUnit) {
    if (allotmentId === null || !data) return;
    const { error } = await api.PATCH("/api/v1/allotments/{allotment_id}", {
      params: { path: { allotment_id: allotmentId } },
      body: { length_unit: unit },
    });
    if (error) setMessage("Only the owner can change the unit.");
    else client.setQueryData(["measurements", session.serverUrl, allotmentId], { ...data, length_unit: unit });
  }

  const footer =
    data && data.measured > 0 ? (
      <Button label={`Apply ${data.measured} measurement${data.measured === 1 ? "" : "s"} to the map`} onPress={() => router.push("/measure/apply")} />
    ) : undefined;

  const done = data ? data.total > 0 && data.measured === data.total : false;

  return (
    <Screen
      title="Measure the plot"
      subtitle="Measure each side of a shape with a tape, plus one diagonal, and the map can be corrected to real sizes."
      footer={footer}
    >
      {checklist.isLoading ? <Loading label="Loading the checklist…" /> : null}
      {checklist.isError ? <Banner tone="danger" text={checklist.error.message} action="Try again" onAction={() => checklist.refetch()} /> : null}
      {message ? <Banner tone="warn" text={message} /> : null}

      {data && data.items.length === 0 ? (
        <Empty
          title="No checklist yet"
          body="Draw your beds, paths and buildings in the web app first. Then make the checklist: one distance for each side of each shape, plus a diagonal to fix its shape."
          action={<Button label="Make the checklist" onPress={refreshFromMap} busy={busy} />}
        />
      ) : null}

      {data && data.items.length > 0 ? (
        <>
          <Card>
            <View style={{ flexDirection: "row", alignItems: "baseline", gap: space.sm }}>
              <T kind="number">{data.measured}</T>
              <T kind="heading" muted>
                of {data.total} measured
              </T>
            </View>
            <ProgressBar value={data.measured} total={data.total} />
            {done ? <T tone="ok" kind="label">All measured. Apply them to correct the map.</T> : null}
          </Card>

          {data.features.map((feature) => {
            const mine = data.items.filter((i) => i.feature_id === feature.id);
            const complete = feature.total > 0 && feature.measured === feature.total;
            return (
              <Section key={feature.id} title={feature.name} right={<Chip label={complete ? "Done" : `${feature.measured} of ${feature.total}`} tone={complete ? "ok" : "neutral"} />}>
                <Card style={{ paddingVertical: space.xs }}>
                  {mine.map((item, i) => {
                    const name = item.kind === "radius" ? "Radius" : `Corner ${item.a + 1} to ${item.b + 1}${item.kind === "diagonal" ? " (diagonal)" : ""}`;
                    const sub = item.stale
                      ? "Corners have changed: ignored"
                      : item.skipped
                        ? "Skipped"
                        : item.drawn_m !== null
                          ? `Map says ${formatLength(item.drawn_m, data.length_unit)}`
                          : undefined;
                    const value = item.value_m !== null ? formatLength(item.value_m, data.length_unit) : undefined;
                    return (
                      <Row
                        key={item.id}
                        first={i === 0}
                        title={name}
                        subtitle={sub}
                        value={value ?? (item.stale || item.skipped ? undefined : "Measure")}
                        valueTone={value ? "ok" : "neutral"}
                        dim={item.stale || item.skipped}
                        onPress={() => router.push(`/measure/${item.id}`)}
                        accessibilityLabel={`${name}, ${value ?? "not measured"}`}
                      />
                    );
                  })}
                </Card>
              </Section>
            );
          })}

          <Section title="Show lengths in">
            <Segmented options={UNITS} value={data.length_unit} onChange={chooseUnit} />
          </Section>
          <Button label="Update from the map" kind="secondary" onPress={refreshFromMap} busy={busy} />
        </>
      ) : null}
    </Screen>
  );
}
