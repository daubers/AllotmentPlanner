import { StyleSheet, useColorScheme } from "react-native";

const light = { bg: "#f6f7f4", card: "#ffffff", text: "#1d2a1f", muted: "#66736a", accent: "#2f7d46", danger: "#b3261e", border: "#d9ded8" };
const dark = { bg: "#121613", card: "#1c231e", text: "#e8efe9", muted: "#9aa89e", accent: "#57b373", danger: "#f2867f", border: "#2c372f" };

export type Palette = typeof light;

export function usePalette(): Palette {
  return useColorScheme() === "dark" ? dark : light;
}

/** Big touch targets: this is used outdoors, often with muddy thumbs. */
export const TOUCH = 48;

export function makeStyles(p: Palette) {
  return StyleSheet.create({
    screen: { flex: 1, backgroundColor: p.bg },
    content: { padding: 16, gap: 12 },
    card: { backgroundColor: p.card, borderRadius: 12, padding: 16, borderWidth: 1, borderColor: p.border, gap: 8 },
    title: { fontSize: 22, fontWeight: "700", color: p.text },
    heading: { fontSize: 16, fontWeight: "600", color: p.text },
    text: { fontSize: 16, color: p.text },
    muted: { fontSize: 14, color: p.muted },
    error: { fontSize: 14, color: p.danger },
    input: {
      minHeight: TOUCH,
      borderWidth: 1,
      borderColor: p.border,
      borderRadius: 10,
      paddingHorizontal: 12,
      fontSize: 16,
      color: p.text,
      backgroundColor: p.card,
    },
    button: { minHeight: TOUCH, borderRadius: 10, backgroundColor: p.accent, alignItems: "center", justifyContent: "center", paddingHorizontal: 16 },
    buttonText: { color: "#fff", fontSize: 16, fontWeight: "600" },
    ghost: { minHeight: TOUCH, borderRadius: 10, borderWidth: 1, borderColor: p.border, alignItems: "center", justifyContent: "center", paddingHorizontal: 16 },
    ghostText: { color: p.text, fontSize: 16 },
    row: { minHeight: TOUCH, flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 8 },
  });
}
