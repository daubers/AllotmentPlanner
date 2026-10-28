import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import React, { useEffect, useState } from "react";
import { View, useWindowDimensions } from "react-native";
import Svg from "react-native-svg";
import type { components } from "../../src/api/schema";
import { useChecklist } from "../../src/measure/hooks";
import { Compare } from "../../src/measure/SketchView";
import { formatLength } from "../../src/measure/units";
import { useApp } from "../../src/state/AppProvider";
import { Banner, Button, Card, Chip, Loading, Screen, T } from "../../src/ui/kit";
import { space, usePalette } from "../../src/ui/theme";

type Fit = components["schemas"]["FitFeature"];

export default function Apply() {
  const { api, allotmentId, session } = useApp();
  const p = usePalette();
  const router = useRouter();
  const client = useQueryClient();
  const { width } = useWindowDimensions();
  const checklist = useChecklist();
  const unit = checklist.data?.length_unit ?? "m";
  const [fits, setFits] = useState<Fit[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [applying, setApplying] = useState(false);
  const [done, setDone] = useState(false);
  const w = Math.min(width, 520) - 2 * space.lg - 2 * space.lg - 2;

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
    setError(null);
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
      title={done ? "Map corrected" : "Apply to the map"}
      subtitle={done ? "Your drawn shapes now match the tape." : "This is what would change. Nothing is altered until you apply it."}
      backLabel="Checklist"
      footer={
        done ? (
          <Button label="Done" onPress={() => router.dismissTo("/")} />
        ) : (
          <Button
            label={changed.length ? `Correct ${changed.length} shape${changed.length === 1 ? "" : "s"} on the map` : "Nothing to change"}
            disabled={!changed.length || blocked}
            busy={applying}
            onPress={apply}
          />
        )
      }
    >
      {!fits && !error ? <Loading label="Working out the corrections…" /> : null}
      {error ? <Banner tone="danger" text={error} /> : null}
      {fits && fits.length === 0 ? <Card><T muted>Nothing has been measured yet.</T></Card> : null}

      {fits?.map((fit) => (
        <Card key={fit.feature_id}>
          <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: space.sm }}>
            <T kind="heading" style={{ flex: 1 }}>
              {fit.name}
            </T>
            {fit.error ? <Chip label="Can't apply" tone="danger" /> : fit.changed ? <Chip label="Will change" tone="ok" /> : <Chip label="Already right" />}
          </View>
          {fit.error ? (
            <Banner tone="danger" text={`${fit.error} Check the measurements.`} />
          ) : (
            <>
              <View style={{ alignItems: "center" }}>
                <Svg width={w} height={200} accessibilityLabel={`${fit.name}: drawn outline dashed, corrected outline solid`}>
                  <Compare drawn={fit.drawn_geometry as any} corrected={fit.geometry as any} width={w} />
                </Svg>
              </View>
              <View style={{ flexDirection: "row", gap: space.lg }}>
                <T kind="caption" muted>
                  ┄ As drawn
                </T>
                <T kind="caption" style={{ color: p.accent, fontWeight: "700" }}>
                  ━ Corrected
                </T>
              </View>
              {fit.changed ? (
                <T>
                  Corners move by up to <T style={{ fontWeight: "700" }}>{formatLength(fit.max_move_m ?? 0, unit)}</T>. Typical error goes from {formatLength(fit.rms_before_m ?? 0, unit)} to {formatLength(fit.rms_after_m ?? 0, unit)}.
                </T>
              ) : null}
            </>
          )}
          {fit.missing ? (
            <Banner tone="warn" text={`${fit.missing} more measurement${fit.missing === 1 ? "" : "s"} needed to fix this shape completely. Corners without one stay as drawn.`} />
          ) : null}
          {fit.recheck?.length ? (
            <Banner tone="warn" text={`${fit.recheck.length} measurement${fit.recheck.length === 1 ? "" : "s"} disagree with the others. One may be misread: measure again.`} />
          ) : null}
        </Card>
      ))}
    </Screen>
  );
}
