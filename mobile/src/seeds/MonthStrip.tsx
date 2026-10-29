import React from "react";
import { Pressable, View } from "react-native";
import { T } from "../ui/kit";
import { radius, space, usePalette } from "../ui/theme";
import { ACTIVITIES, MONTH_NAMES, currentMonth, type Activity, type Calendar } from "./model";

const COLOUR: Record<Activity, string> = { sow_indoors: "#d98e04", sow_outdoors: "#2f7d3b", plant_out: "#2b7bb9", harvest: "#b3261e" };

/** Four rows (sow indoors, sow outdoors, plant out, harvest) by twelve months. Tap a cell to flip it when editable. */
export default function MonthStrip({ calendar, onToggle }: { calendar: Calendar; onToggle?: (activity: Activity, month: number) => void }) {
  const p = usePalette();
  const now = currentMonth();
  return (
    <View style={{ gap: space.xs }} accessibilityLabel="Sowing calendar">
      <View style={{ flexDirection: "row", alignItems: "center" }}>
        <View style={{ width: 92 }} />
        {MONTH_NAMES.map((m, i) => (
          <View key={m} style={{ flex: 1, alignItems: "center" }}>
            <T kind="caption" muted style={i + 1 === now ? { fontWeight: "800", color: p.text } : undefined}>{m[0]}</T>
          </View>
        ))}
      </View>
      {ACTIVITIES.map((a) => (
        <View key={a.key} style={{ flexDirection: "row", alignItems: "center", gap: 0 }}>
          <T kind="caption" style={{ width: 92 }} numberOfLines={1}>{a.label}</T>
          {MONTH_NAMES.map((m, i) => {
            const on = calendar[a.key]?.includes(i + 1) ?? false;
            const cell = (
              <View
                style={{
                  height: onToggle ? 30 : 20,
                  margin: 1,
                  borderRadius: radius.sm / 2,
                  backgroundColor: on ? COLOUR[a.key] : p.surfaceAlt,
                  borderWidth: i + 1 === now ? 1.5 : 0,
                  borderColor: p.muted,
                }}
              />
            );
            return onToggle ? (
              <Pressable
                key={m}
                style={{ flex: 1 }}
                onPress={() => onToggle(a.key, i + 1)}
                accessibilityRole="button"
                accessibilityLabel={`${a.label} in ${m}`}
                accessibilityState={{ selected: on }}
              >
                {cell}
              </Pressable>
            ) : (
              <View key={m} style={{ flex: 1 }} accessible accessibilityLabel={`${a.label} in ${m}: ${on ? "yes" : "no"}`}>
                {cell}
              </View>
            );
          })}
        </View>
      ))}
    </View>
  );
}
