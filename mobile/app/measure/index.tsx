import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import React, { useState } from "react";
import { ActivityIndicator, Pressable, Text, View } from "react-native";
import { useApp } from "../../src/state/AppProvider";
import { useChecklist } from "../../src/measure/hooks";
import { formatLength, type LengthUnit } from "../../src/measure/units";
import { Button, Card, ProgressBar, Screen, useStyles } from "../../src/ui/kit";

const UNITS: { value: LengthUnit; label: string }[] = [
  { value: "m", label: "m" },
  { value: "cm", label: "cm" },
  { value: "ft_in", label: "ft / in" },
];

export default function Measure() {
  const { api, allotmentId, session } = useApp();
  const { s, palette } = useStyles();
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
    if (error) setMessage("Only the owner can change the unit");
    else client.setQueryData(["measurements", session.serverUrl, allotmentId], { ...data, length_unit: unit });
  }

  const footer = data && data.measured > 0 ? <Button label="Apply to map…" onPress={() => router.push("/measure/apply")} /> : undefined;

  return (
    <Screen title="Measure the plot" footer={footer}>
      {checklist.isLoading ? <ActivityIndicator /> : null}
      {checklist.isError ? <Text style={s.error}>{checklist.error.message}</Text> : null}
      {message ? <Text style={s.error}>{message}</Text> : null}

      {data && data.items.length === 0 ? (
        <Card>
          <Text style={s.heading}>No checklist yet</Text>
          <Text style={s.text}>
            Draw your beds, paths and buildings in the web app first. Then make the checklist: it lists the distances to take, one per side of each shape, plus a diagonal to fix its shape.
          </Text>
          <Button label="Make the checklist" onPress={refreshFromMap} busy={busy} />
        </Card>
      ) : null}

      {data && data.items.length > 0 ? (
        <>
          <Card>
            <Text style={s.heading}>
              {data.measured} of {data.total} measured
            </Text>
            <ProgressBar value={data.measured} total={data.total} />
            <View style={{ flexDirection: "row", gap: 8, marginTop: 4 }}>
              {UNITS.map((u) => (
                <Pressable
                  key={u.value}
                  onPress={() => chooseUnit(u.value)}
                  accessibilityRole="radio"
                  accessibilityState={{ selected: data.length_unit === u.value }}
                  style={{
                    flex: 1,
                    minHeight: 44,
                    alignItems: "center",
                    justifyContent: "center",
                    borderRadius: 10,
                    borderWidth: 1,
                    borderColor: data.length_unit === u.value ? palette.accent : palette.border,
                    backgroundColor: data.length_unit === u.value ? palette.accent : "transparent",
                  }}
                >
                  <Text style={{ color: data.length_unit === u.value ? "#fff" : palette.text, fontSize: 15 }}>{u.label}</Text>
                </Pressable>
              ))}
            </View>
          </Card>

          {data.features.map((feature) => (
            <Card key={feature.id}>
              <View style={s.row}>
                <Text style={s.heading}>{feature.name}</Text>
                <Text style={s.muted}>
                  {feature.measured} / {feature.total}
                </Text>
              </View>
              {data.items
                .filter((i) => i.feature_id === feature.id)
                .map((item) => (
                  <Pressable
                    key={item.id}
                    style={[s.row, { opacity: item.stale || item.skipped ? 0.5 : 1 }]}
                    onPress={() => router.push(`/measure/${item.id}`)}
                    accessibilityRole="button"
                    accessibilityLabel={`${item.kind === "radius" ? "Radius" : `Corner ${item.label}`}, ${item.value_m !== null ? formatLength(item.value_m, data.length_unit) : "not measured"}`}
                  >
                    <View style={{ flex: 1 }}>
                      <Text style={s.text}>{item.kind === "radius" ? "Radius" : `Corner ${item.label}`}</Text>
                      <Text style={s.muted}>
                        {item.stale ? "Corners changed: ignored" : item.skipped ? "Skipped" : item.drawn_m !== null ? `Map says ${formatLength(item.drawn_m, data.length_unit)}` : ""}
                      </Text>
                    </View>
                    <Text style={[s.text, { color: item.value_m !== null ? palette.accent : palette.muted, fontWeight: "600" }]}>
                      {item.value_m !== null ? formatLength(item.value_m, data.length_unit) : "Measure ›"}
                    </Text>
                  </Pressable>
                ))}
            </Card>
          ))}
          <Button label="Update from the map" kind="secondary" onPress={refreshFromMap} busy={busy} />
        </>
      ) : null}
    </Screen>
  );
}
