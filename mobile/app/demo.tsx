import { Redirect, useLocalSearchParams } from "expo-router";
import React from "react";
import { View } from "react-native";
import { CaptureSummary, Hud, Pill } from "../src/capture/ui";
import { Banner, T } from "../src/ui/kit";
import { radius, space } from "../src/ui/theme";

/** Browser-preview only: shows the camera overlay and walk summary, which can't run without a camera. */
export default function Demo() {
  const { view } = useLocalSearchParams<{ view?: string }>();
  if (process.env.EXPO_PUBLIC_DEMO !== "1") return <Redirect href="/" />;
  if (view === "summary" || view === "summary-bad") {
    const bad = view === "summary-bad";
    return (
      <CaptureSummary
        summary={bad ? { photos: 9, walkedM: 4, spreadM: 1.5, sectors: 2, tooClose: 6, roughFixes: 4 } : { photos: 24, walkedM: 112, spreadM: 22, sectors: 10, tooClose: 1, roughFixes: 0 }}
        uploads={{ total: 24, waiting: 6, failed: 0 }}
        queueState={{ pending: 6, failed: 0, active: { id: "x", kind: "upload", progress: 0.4 } }}
        mapMessage={null}
        minPhotos={5}
        onBuild={() => {}}
        onKeepGoing={() => {}}
        onNewWalk={() => {}}
        onDone={() => {}}
        onReview={() => {}}
      />
    );
  }
  const trouble = view === "hud-bad";
  return (
    <View style={{ flex: 1, backgroundColor: "#5b6b4f", padding: space.md, gap: space.sm, paddingTop: 48 }}>
      <View style={{ flexDirection: "row", gap: space.sm }}>
        <Hud label="GPS" value={trouble ? "searching" : "±4 m"} tone={trouble ? "danger" : "ok"} />
        <Hud label="Compass" value={trouble ? "none" : "142°"} tone={trouble ? "warn" : "ok"} />
        <Hud label="Camera" value={trouble ? "too high" : "level"} tone={trouble ? "warn" : "ok"} />
      </View>
      {trouble ? <Banner tone="danger" text="Waiting for a GPS fix…" /> : null}
      <View style={{ flex: 1 }} />
      <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingBottom: 24 }}>
        <View style={{ flex: 1, alignItems: "flex-start" }}>
          <Pill label="Close" onPress={() => {}} />
        </View>
        <View style={{ width: 80, height: 80, borderRadius: 40, borderWidth: 5, borderColor: "#fff", alignItems: "center", justifyContent: "center", opacity: trouble ? 0.4 : 1 }}>
          <View style={{ width: 58, height: 58, borderRadius: 29, backgroundColor: "#fff" }} />
        </View>
        <View style={{ flex: 1, alignItems: "flex-end" }}>
          <Pill label="Finish · 12" onPress={() => {}} />
        </View>
      </View>
    </View>
  );
}
