import { useQueryClient } from "@tanstack/react-query";
import { useLocalSearchParams, useRouter } from "expo-router";
import React, { useEffect, useState } from "react";
import { Image, View } from "react-native";
import MonthStrip from "../../src/seeds/MonthStrip";
import { useMediaUrl, usePacket, useScans } from "../../src/seeds/hooks";
import { ACTIVITIES, daysLabel, packetTitle, STOCK_LABEL, toggleMonth, type Calendar } from "../../src/seeds/model";
import { useApp } from "../../src/state/AppProvider";
import { Banner, Button, Card, Chip, Field, Loading, Screen, Section, Segmented, T } from "../../src/ui/kit";
import { space } from "../../src/ui/theme";

const num = (s: string): number | null => (s.trim() === "" ? null : Number(s));
const text = (n: number | null | undefined): string => (n == null ? "" : String(n));
const NOT_FOUND: Record<string, string> = { name: "name", supplier: "supplier", seeds_in_packet: "seed count", sow_depth_mm: "sowing depth", best_before_year: "sow-by year", germinate_days: "days to germinate", calendar: "calendar" };

export default function Packet() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const packetId = Number(id);
  const router = useRouter();
  const { api, allotmentId, session } = useApp();
  const client = useQueryClient();
  const packet = usePacket(packetId);
  const scans = useScans();
  const mediaUrl = useMediaUrl();
  const p = packet.data;
  const isDraft = p?.status === "draft";
  const scan = scans.data?.find((s) => s.packet_id === packetId);
  const cropUrl = (scan?.crop as { url?: string } | null | undefined)?.url;
  const canEdit = true; // the server refuses a viewer's save, and says so

  const [form, setForm] = useState<Record<string, string>>({});
  const [calendar, setCalendar] = useState<Calendar>({});
  const [stock, setStock] = useState("full");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!p) return;
    setForm({
      name: p.name ?? "", variety: p.variety ?? "", supplier: p.supplier ?? "",
      sow_depth_mm: text(p.sow_depth_mm), spacing_plant_cm: text(p.spacing_plant_cm),
      germinate_days_min: text(p.germinate_days_min), germinate_days_max: text(p.germinate_days_max),
      best_before_year: text(p.best_before_year), seeds_in_packet: text(p.seeds_in_packet), notes: p.notes ?? "",
    });
    setCalendar((p.calendar ?? {}) as Calendar);
    setStock(p.stock ?? "full");
  }, [p?.id, p?.updated_at]); // eslint-disable-line react-hooks/exhaustive-deps

  const set = (k: string) => (v: string) => setForm((f) => ({ ...f, [k]: v }));

  async function save() {
    if (allotmentId === null) return;
    setSaving(true);
    setError(null);
    const { data, error: err } = await api.PATCH("/api/v1/allotments/{allotment_id}/packets/{packet_id}", {
      params: { path: { allotment_id: allotmentId, packet_id: packetId } },
      body: {
        name: form.name.trim(), variety: form.variety.trim(), supplier: form.supplier.trim(), notes: form.notes,
        sow_depth_mm: num(form.sow_depth_mm), spacing_plant_cm: num(form.spacing_plant_cm),
        germinate_days_min: num(form.germinate_days_min), germinate_days_max: num(form.germinate_days_max),
        best_before_year: num(form.best_before_year), seeds_in_packet: num(form.seeds_in_packet),
        stock: stock as "full", calendar,
        ...(isDraft ? { status: "active" as const } : {}),
      },
    });
    setSaving(false);
    if (!data) {
      setError(((err as { message?: string } | undefined)?.message) ?? "Couldn't save. Are you online?");
      return;
    }
    void client.invalidateQueries({ queryKey: ["packets"] });
    void client.invalidateQueries({ queryKey: ["packet"] });
    setSaved(true);
    if (isDraft) router.back();
  }

  if (packet.isLoading) return <Screen title="Packet"><Loading /></Screen>;
  if (!p) return <Screen title="Packet"><Banner tone="danger" text="Couldn't load that packet." action="Try again" onAction={() => packet.refetch()} /></Screen>;

  return (
    <Screen
      title={packetTitle(p)}
      subtitle={[p.supplier, daysLabel(p.maturity_days_min, p.maturity_days_max) && `Ready in ${daysLabel(p.maturity_days_min, p.maturity_days_max)}`].filter(Boolean).join(" · ") || undefined}
      footer={canEdit ? <Button label={isDraft ? "Save to library" : "Save"} onPress={() => void save()} busy={saving} /> : undefined}
    >
      {isDraft ? (
        <Banner tone="warn" text={`Read from a photo. Check every field, then save.${scan?.missing?.length ? " Not found: " + scan.missing.map((m) => NOT_FOUND[m] ?? m).join(", ") + "." : ""}`} />
      ) : null}
      {error ? <Banner tone="danger" text={error} /> : null}
      {saved && !isDraft ? <Banner tone="ok" text="Saved" /> : null}

      <Section title="About">
        <Card>
          <Field label="Name" value={form.name ?? ""} onChangeText={set("name")} />
          <Field label="Variety" value={form.variety ?? ""} onChangeText={set("variety")} />
          <Field label="Supplier" value={form.supplier ?? ""} onChangeText={set("supplier")} />
          <T kind="label">Stock</T>
          <Segmented value={stock} onChange={setStock} options={Object.entries(STOCK_LABEL).map(([value, label]) => ({ value, label }))} />
        </Card>
      </Section>

      <Section title="Growing">
        <Card>
          <Field label="Sowing depth" suffix="mm" keyboardType="numeric" value={form.sow_depth_mm ?? ""} onChangeText={set("sow_depth_mm")} />
          <Field label="Germinates in, from" suffix="days" keyboardType="numeric" value={form.germinate_days_min ?? ""} onChangeText={set("germinate_days_min")} />
          <Field label="Germinates in, to" suffix="days" keyboardType="numeric" value={form.germinate_days_max ?? ""} onChangeText={set("germinate_days_max")} />
          <Field label="Sow by (year)" keyboardType="numeric" value={form.best_before_year ?? ""} onChangeText={set("best_before_year")} />
          <Field label="Seeds in the packet" keyboardType="numeric" value={form.seeds_in_packet ?? ""} onChangeText={set("seeds_in_packet")} />
        </Card>
      </Section>

      <Section title="When">
        <Card>
          {cropUrl ? (
            <View style={{ gap: space.xs }}>
              <Image source={{ uri: mediaUrl(cropUrl) }} style={{ width: "100%", height: 90, resizeMode: "contain" }} accessibilityLabel="The calendar as read from your photo" />
              <T kind="caption" muted>As read from your photo. Tap a month to correct it.</T>
            </View>
          ) : null}
          {isDraft && scan && !scan.calendar_source ? <T kind="caption" tone="danger">No calendar was found on the photo: set the months by hand.</T> : null}
          <MonthStrip calendar={calendar} onToggle={(a, m) => setCalendar((c) => ({ ...c, [a]: toggleMonth(c[a], m) }))} />
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.xs }}>
            {ACTIVITIES.filter((a) => (calendar[a.key]?.length ?? 0) > 0).map((a) => <Chip key={a.key} label={a.label} />)}
          </View>
        </Card>
      </Section>

      <Section title="Photos">
        <Card>
          {p.photos?.length ? (
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.sm }}>
              {p.photos.map((m) => (m.thumb_url ? <Image key={m.id} source={{ uri: mediaUrl(m.thumb_url) }} style={{ width: 96, height: 96, borderRadius: 8 }} accessibilityLabel={m.caption || m.filename} /> : null))}
            </View>
          ) : (
            <T muted>No photos yet.</T>
          )}
          <Button label="Add a photo" kind="secondary" onPress={() => router.push(`/photo?packetId=${packetId}`)} />
        </Card>
      </Section>
    </Screen>
  );
}
