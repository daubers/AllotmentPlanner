import { useLocalSearchParams, useRouter } from "expo-router";
import React, { useEffect, useMemo, useState } from "react";
import { Text, useWindowDimensions, View } from "react-native";
import Svg from "react-native-svg";
import { nextToMeasure } from "../../src/measure/model";
import { useChecklist, useRecord, useShapes } from "../../src/measure/hooks";
import { Sketch } from "../../src/measure/SketchView";
import { UNIT_HINT, editText, formatLength, parseLength } from "../../src/measure/units";
import { Button, Card, Field, Screen, useStyles } from "../../src/ui/kit";

export default function MeasureItem() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const { s, palette } = useStyles();
  const { width } = useWindowDimensions();
  const checklist = useChecklist();
  const shapes = useShapes();
  const record = useRecord();
  const data = checklist.data;
  const item = data?.items.find((i) => i.id === Number(id));

  const [text, setText] = useState("");
  const [note, setNote] = useState("");
  useEffect(() => {
    if (item && data) {
      setText(item.value_m !== null ? editText(item.value_m, data.length_unit) : "");
      setNote(item.note);
    }
  }, [item?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const parsed = useMemo(() => (data && text.trim() ? parseLength(text, data.length_unit) : null), [text, data]);
  const invalid = text.trim() !== "" && (parsed === null || parsed < 0.01 || parsed > 1000);

  if (!item || !data) {
    return (
      <Screen title="Measure">
        <Text style={s.muted}>{checklist.isLoading ? "Loading…" : "That measurement isn't on the list any more."}</Text>
      </Screen>
    );
  }

  const label = item.kind === "radius" ? "the radius" : `corner ${item.a + 1} to corner ${item.b + 1}`;
  const diff = parsed !== null && item.drawn_m !== null && !invalid ? parsed - item.drawn_m : null;

  async function finish(patch: { value_m?: number | null; skipped?: boolean }) {
    await record(item!, { ...patch, note });
    const next = nextToMeasure(
      data!.items.map((i) => (i.id === item!.id ? { ...i, ...patch, value_m: patch.value_m !== undefined ? patch.value_m : i.value_m, skipped: patch.skipped ?? i.skipped } : i)),
      item!.id,
    );
    if (next) router.replace(`/measure/${next.id}`);
    else router.back();
  }

  return (
    <Screen
      title={item.feature_name}
      footer={
        <>
          <Button label="Save and next" disabled={parsed === null || invalid} onPress={() => finish({ value_m: parsed })} />
          <View style={{ flexDirection: "row", gap: 8 }}>
            <View style={{ flex: 1 }}>
              <Button label={item.skipped ? "Unskip" : "Skip"} kind="secondary" onPress={() => finish({ skipped: !item.skipped })} />
            </View>
            {item.value_m !== null ? (
              <View style={{ flex: 1 }}>
                <Button label="Clear" kind="secondary" onPress={() => finish({ value_m: null })} />
              </View>
            ) : null}
          </View>
        </>
      }
    >
      <Card>
        <Text style={s.heading}>Measure {label}</Text>
        <Svg width={width - 64} height={220} accessibilityLabel={`Sketch of ${item.feature_name} with corners numbered`}>
          <Sketch
            geometry={shapes.data?.get(item.feature_id)}
            highlight={item.kind === "radius" ? undefined : [item.a, item.b]}
            width={width - 64}
          />
        </Svg>
        {item.drawn_m !== null ? <Text style={s.muted}>The map says {formatLength(item.drawn_m, data.length_unit)}</Text> : null}
        {item.stale ? <Text style={s.error}>This shape's corners have changed since, so this one is ignored.</Text> : null}
      </Card>

      <Field
        label={`Length (${UNIT_HINT[data.length_unit]})`}
        value={text}
        onChangeText={setText}
        keyboardType={data.length_unit === "ft_in" ? "default" : "decimal-pad"}
        autoCorrect={false}
        autoCapitalize="none"
        returnKeyType="done"
        accessibilityHint="Type the length from your tape measure"
      />
      {invalid ? (
        <Text style={s.error}>That doesn't look like a length between 1 cm and 1000 m.</Text>
      ) : parsed !== null ? (
        <Text style={[s.muted, { color: palette.text }]}>
          = {formatLength(parsed, data.length_unit)}
          {diff !== null && Math.abs(diff) >= 0.005 ? `  (${diff > 0 ? "+" : "−"}${formatLength(Math.abs(diff), data.length_unit)} against the map)` : ""}
        </Text>
      ) : null}
      <Field label="Note (optional)" value={note} onChangeText={setNote} placeholder="e.g. from the post to the fence" />
    </Screen>
  );
}
