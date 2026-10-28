import { useLocalSearchParams, useRouter } from "expo-router";
import React, { useEffect, useMemo, useState } from "react";
import { View, useWindowDimensions } from "react-native";
import Svg from "react-native-svg";
import { useChecklist, useRecord, useShapes } from "../../src/measure/hooks";
import { nextToMeasure } from "../../src/measure/model";
import { Sketch } from "../../src/measure/SketchView";
import { UNIT_HINT, editText, formatLength, parseLength } from "../../src/measure/units";
import { Banner, Button, Card, Field, Loading, Screen, T } from "../../src/ui/kit";
import { space } from "../../src/ui/theme";

const UNIT_SUFFIX = { m: "m", cm: "cm", ft_in: "" } as const;

export default function MeasureItem() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
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
        {checklist.isLoading ? <Loading /> : <T muted>That measurement isn't on the list any more.</T>}
      </Screen>
    );
  }

  const live = data.items.filter((i) => !i.stale);
  const position = live.findIndex((i) => i.id === item.id) + 1;
  const what = item.kind === "radius" ? "the radius" : `corner ${item.a + 1} to corner ${item.b + 1}`;
  const diff = parsed !== null && item.drawn_m !== null && !invalid ? parsed - item.drawn_m : null;
  const farOff = diff !== null && item.drawn_m !== null && Math.abs(diff) > Math.max(0.5, item.drawn_m * 0.25);
  const sketchWidth = Math.min(width, 520) - 2 * space.lg - 2 * space.lg - 2;

  async function finish(patch: { value_m?: number | null; skipped?: boolean }) {
    await record(item!, { ...patch, note });
    const merged = data!.items.map((i) => (i.id === item!.id ? { ...i, ...patch } : i));
    const next = nextToMeasure(merged, item!.id);
    if (next) router.replace(`/measure/${next.id}`);
    else router.back();
  }

  return (
    <Screen
      backLabel="Checklist"
      title={item.feature_name}
      subtitle={position ? `Distance ${position} of ${live.length}` : undefined}
      footer={
        <>
          <Button label="Save and next" disabled={parsed === null || invalid} onPress={() => finish({ value_m: parsed })} />
          <View style={{ flexDirection: "row", gap: space.sm }}>
            <View style={{ flex: 1 }}>
              <Button label={item.skipped ? "Unskip" : "Skip"} kind="secondary" small onPress={() => finish({ skipped: !item.skipped })} />
            </View>
            {item.value_m !== null ? (
              <View style={{ flex: 1 }}>
                <Button label="Clear" kind="secondary" small onPress={() => finish({ value_m: null })} />
              </View>
            ) : null}
          </View>
        </>
      }
    >
      <Card>
        <T kind="heading">Measure {what}</T>
        <View style={{ alignItems: "center" }}>
          <Svg width={sketchWidth} height={230} accessibilityLabel={`Sketch of ${item.feature_name} with its corners numbered`}>
            <Sketch geometry={shapes.data?.get(item.feature_id)} highlight={item.kind === "radius" ? undefined : [item.a, item.b]} width={sketchWidth} height={230} />
          </Svg>
        </View>
        {item.drawn_m !== null ? (
          <T muted>
            The map says <T style={{ fontWeight: "700" }}>{formatLength(item.drawn_m, data.length_unit)}</T>
          </T>
        ) : null}
        {item.stale ? <Banner tone="warn" text="This shape's corners have changed since, so this one is ignored." /> : null}
      </Card>

      <Field
        large
        autoFocus
        label="What your tape says"
        helper={`Type it in ${UNIT_HINT[data.length_unit]}`}
        suffix={UNIT_SUFFIX[data.length_unit]}
        value={text}
        onChangeText={setText}
        keyboardType={data.length_unit === "ft_in" ? "default" : "decimal-pad"}
        autoCorrect={false}
        autoCapitalize="none"
        returnKeyType="done"
        error={invalid ? "That doesn't look like a length between 1 cm and 1000 m." : undefined}
      />
      {parsed !== null && !invalid ? (
        <View style={{ gap: space.xs }}>
          <T>
            = <T style={{ fontWeight: "700" }}>{formatLength(parsed, data.length_unit)}</T>
            {diff !== null && Math.abs(diff) >= 0.005 ? <T muted>{`   ${diff > 0 ? "+" : "−"}${formatLength(Math.abs(diff), data.length_unit)} against the map`}</T> : null}
          </T>
          {farOff ? <Banner tone="warn" text="That is a long way from the map. Check the tape and which corners you measured." /> : null}
        </View>
      ) : null}
      <Field label="Note (optional)" value={note} onChangeText={setNote} placeholder="e.g. from the post to the fence" />
    </Screen>
  );
}
