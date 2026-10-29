import { useLocalSearchParams, useRouter } from "expo-router";
import React, { useState } from "react";
import { Pressable, ScrollView, View } from "react-native";
import { usePackets } from "../../src/seeds/hooks";
import { packetTitle } from "../../src/seeds/model";
import { useCellChange, useTray } from "../../src/trays/hooks";
import { cellMap, colourFor, describeCell, glyph, key, summarise, toggle, toggleCol, toggleRow } from "../../src/trays/model";
import { Banner, Button, Card, Field, Loading, Row, Screen, Section, T } from "../../src/ui/kit";
import { radius, space, usePalette } from "../../src/ui/theme";

const SIZE = 44;

export default function Tray() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const trayId = Number(id);
  const router = useRouter();
  const p = usePalette();
  const tray = useTray(trayId);
  const packets = usePackets("active");
  const change = useCellChange(trayId);
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set());
  const [choosing, setChoosing] = useState(false);
  const [packetId, setPacketId] = useState<number | null>(null);
  const [count, setCount] = useState("1");
  const t = tray.data;

  if (tray.isLoading) return <Screen title="Tray"><Loading /></Screen>;
  if (!t) return <Screen title="Tray"><Banner tone="danger" text="Couldn't load that tray." action="Try again" onAction={() => tray.refetch()} /></Screen>;

  const rows = t.rows ?? 0;
  const cols = t.cols ?? 0;
  const cells = cellMap((t.cells ?? []) as any);
  const names = new Map((packets.data ?? []).map((pk) => [pk.id, packetTitle(pk)]));
  const nameOf = (pid?: number | null) => (pid == null ? undefined : names.get(pid) ?? t.kinds?.find((k) => k.packet_id === pid)?.name);
  const n = selected.size;

  async function apply(set: Parameters<typeof change>[1]) {
    await change(selected, set);
    setSelected(new Set());
  }

  return (
    <Screen title={t.name ?? "Tray"} subtitle={`${rows} × ${cols} · ${summarise(t.counts) || "nothing sown yet"}`}>
      <ScrollView horizontal showsHorizontalScrollIndicator>
        <View style={{ gap: 3 }}>
          <View style={{ flexDirection: "row", gap: 3 }}>
            <View style={{ width: SIZE * 0.7 }} />
            {Array.from({ length: cols }, (_, c) => (
              <Pressable key={c} onPress={() => setSelected(toggleCol(selected, c, rows))} accessibilityRole="button" accessibilityLabel={`Select column ${c + 1}`} style={{ width: SIZE, height: 28, alignItems: "center", justifyContent: "center" }}>
                <T kind="caption" muted>{c + 1}</T>
              </Pressable>
            ))}
          </View>
          {Array.from({ length: rows }, (_, r) => (
            <View key={r} style={{ flexDirection: "row", gap: 3, alignItems: "center" }}>
              <Pressable onPress={() => setSelected(toggleRow(selected, r, cols))} accessibilityRole="button" accessibilityLabel={`Select row ${r + 1}`} style={{ width: SIZE * 0.7, height: SIZE, alignItems: "center", justifyContent: "center" }}>
                <T kind="caption" muted>{r + 1}</T>
              </Pressable>
              {Array.from({ length: cols }, (_, c) => {
                const cell = cells.get(key(r, c));
                const on = selected.has(key(r, c));
                return (
                  <Pressable
                    key={c}
                    onPress={() => setSelected(toggle(selected, key(r, c)))}
                    accessibilityRole="button"
                    accessibilityLabel={describeCell(r, c, cell, nameOf(cell?.packet_id))}
                    accessibilityState={{ selected: on }}
                    style={{
                      width: SIZE,
                      height: SIZE,
                      borderRadius: radius.sm,
                      alignItems: "center",
                      justifyContent: "center",
                      backgroundColor: colourFor(cell?.packet_id, t.kinds ?? []) ?? (cell ? "#e6e6e6" : p.surface),
                      borderWidth: on ? 3 : 1,
                      borderColor: on ? p.accent : cell?.status === "germinated" ? p.accent : p.border,
                      opacity: cell?.status === "planted_out" ? 0.5 : 1,
                    }}
                  >
                    <T kind="label" style={{ color: "#13201a" }}>{glyph(cell)}</T>
                  </Pressable>
                );
              })}
            </View>
          ))}
        </View>
      </ScrollView>
      <T kind="caption" muted>✓ came up · ✕ failed · a number is seeds sown · tap a row or column number to pick it all.</T>

      <Section title={n === 0 ? "Choose cells to change them" : `${n} cell${n === 1 ? "" : "s"} selected`}>
        {n > 0 ? (
          <Card>
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.sm }}>
              <Button label="Came up ✓" small onPress={() => void apply({ status: "germinated" })} />
              <Button label="Failed ✕" small kind="secondary" onPress={() => void apply({ status: "failed" })} />
              <Button label="Back to sown" small kind="secondary" onPress={() => void apply({ status: "sown" })} />
              <Button label="Clear" small kind="secondary" onPress={() => void apply({ status: "empty" })} />
            </View>
            <T kind="label">Sow a packet in them</T>
            <Button label={packetId != null ? (names.get(packetId) ?? "Packet") : "Choose a packet…"} kind="secondary" onPress={() => setChoosing(!choosing)} />
            {choosing ? (
              <Card>
                {(packets.data ?? []).map((pk, i) => (
                  <Row key={pk.id} first={i === 0} title={packetTitle(pk)} onPress={() => { setPacketId(pk.id ?? null); setChoosing(false); }} />
                ))}
              </Card>
            ) : null}
            <Field label="Seeds per cell" keyboardType="numeric" value={count} onChangeText={setCount} />
            <Button label="Sow" disabled={packetId == null} onPress={() => packetId != null && void apply({ packet_id: packetId, count: Number(count) || 1 })} />
            <Button label="Clear selection" kind="quiet" small onPress={() => setSelected(new Set())} />
          </Card>
        ) : null}
      </Section>

      <Section title="What's in it">
        <Card>
          {t.kinds?.length ? (
            t.kinds.map((k, i) => (
              <Row key={k.packet_id} first={i === 0} title={k.name || "Unknown seed"} subtitle={`${k.cells} cell${k.cells === 1 ? "" : "s"}, ${k.seeds} seed${k.seeds === 1 ? "" : "s"}`} onPress={() => router.push(`/seeds/${k.packet_id}`)} />
            ))
          ) : (
            <T muted>Nothing sown yet.</T>
          )}
        </Card>
        <Button label="Add a photo of the tray" kind="secondary" onPress={() => router.push(`/photo?trayId=${trayId}`)} />
      </Section>
    </Screen>
  );
}
