import React from "react";
import { View } from "react-native";

/** In the browser preview, show the app at phone width instead of stretched across the window. */
export function DemoFrame({ children }: { children: React.ReactNode }) {
  if (process.env.EXPO_PUBLIC_DEMO !== "1") return <>{children}</>;
  return (
    <View style={{ flex: 1, alignItems: "flex-start", backgroundColor: "#000" }}>
      <View style={{ flex: 1, width: 390, maxWidth: "100%", overflow: "hidden" }}>{children}</View>
    </View>
  );
}
