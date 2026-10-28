import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import React, { useEffect, useState } from "react";
import { ActivityIndicator, Text, useWindowDimensions, View } from "react-native";
import Svg from "react-native-svg";
import type { components } from "../../src/api/schema";
import { useChecklist } from "../../src/measure/hooks";
import { Compare } from "../../src/measure/SketchView";
import { formatLength } from "../../src/measure/units";
import { useApp } from "../../src/state/AppProvider";
import { Button, Card, Screen, useStyles } from "../../src/ui/kit";

type Fit = components["schemas"]["FitFeature"];

export default function Apply() {
  const { api, allotmentId, session } = useApp();
  const { s } = useStyles();
  const router = useRouter();
  const client = useQueryClient();
  const { width } = useWindowDimensions();
  const checklist = useChecklist();
  const unit = checklist.data?.length_unit ?? "m";
  const [fits, setFits] = useState<Fit[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [applying, setApplying] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (allotmentId === null) return;
    (async () => {
      const { data, error: err } = await api.POST("/api/v1/allotments/{allotment_id}/measurements/fit", {
        params: { path: { allotment_id: allotmentId }, query: { preview: true } },
      });
      if (data) setFits(data.features ?? []);
      else setError((err as { message?: string } | undefined)?.message ?? "Couldn't work out the corrections. Are you online?");
    })();
  }, [allotmentId, api]);

  async function apply() {
    if (allotmentId === null) return;
    setApplying(true);
    const { data, error: err } = await api.POST("/api/v1/allotments/{allotment_id}/measurements/fit", {
      params: { path: { allotment_id: allotmentId }, query: { preview: false } },
    });
    setApplying(false);
    if (data) {
      setDone(true);
      void client.invalidateQueries({ queryKey: ["shapes", session.serverUrl, allotmentId] });
      void checklist.refetch();
    } else setError((err as { message?: string } | undefined)?.message ?? "Couldn't change the map");
  }

  const changed = fits?.filter((f) => f.changed) ?? [];
  const blocked = fits?.some((f) => f.error) ?? false;

  return (
    <Screen
      title="Apply to map"
      footer={
        done ? (
          <Button label="Done" onPress={() => router.dismissTo("/")} />
        ) : (
          <Button label={changed.length ? `Change ${changed.length} shape${changed.length === 1 ? "" : "s"} on the map` : "Nothing to change"} disabled={!changed.length || blocked} busy={applying} onPress={apply} />
        )
      }
    >
      {!fits && !error ? <ActivityIndicator /> : null}
      {error ? <Text style={s.error}>{error}</Text> : null}
      {done ? <Text style={s.heading}>The map has been corrected.</Text> : null}
      {fits && fits.length === 0 ? <Text style={s.text}>Nothing has been measured yet.</Text> : null}

      {fits?.map((fit) => (
        <Card key={fit.feature_id}>
          <Text style={s.heading}>{fit.name}</Text>
          {fit.error ? (
            <Text style={s.error}>{fit.error} Check the measurements.</Text>
          ) : (
            <>
              <Svg width={width - 64} height={200} accessibilityLabel={`${fit.name}: drawn outline dashed, corrected outline solid`}>
                <Compare drawn={fit.drawn_geometry as any} corrected={fit.geometry as any} width={width - 64} />
              </Svg>
              <Text style={s.muted}>Dashed: as drawn. Solid: corrected.</Text>
              <Text style={s.text}>
                {fit.changed
                  ? `Corners move by up to ${formatLength(fit.max_move_m ?? 0, unit)}. Typical error ${formatLength(fit.rms_before_m ?? 0, unit)} → ${formatLength(fit.rms_after_m ?? 0, unit)}.`
                  : "Already matches your measurements."}
              </Text>
            </>
          )}
          {fit.missing ? (
            <Text style={s.error}>
              {fit.missing} more measurement{fit.missing === 1 ? "" : "s"} needed to fix this shape completely: the corners without one stay as drawn.
            </Text>
          ) : null}
          {fit.recheck?.length ? (
            <View>
              <Text style={s.error}>
                {fit.recheck.length} measurement{fit.recheck.length === 1 ? "" : "s"} don't agree with the others: one of them may be misread. Check them again.
              </Text>
            </View>
          ) : null}
        </Card>
      ))}
    </Screen>
  );
}
