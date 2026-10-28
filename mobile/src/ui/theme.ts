import { useColorScheme } from "react-native";

/** Colours, type and spacing for the whole app. The app is used outdoors, often in bright sun and
 *  with muddy hands, so: strong contrast (text and buttons all clear 4.5:1), big touch targets
 *  (48 px), and no information carried by colour alone (status always has words as well). */

export type Palette = {
  bg: string;
  surface: string;
  surfaceAlt: string;
  text: string;
  muted: string;
  border: string;
  accent: string;
  onAccent: string;
  accentSoft: string;
  danger: string;
  onDanger: string;
  dangerSoft: string;
  warn: string;
  warnSoft: string;
  overlay: string;
};

const light: Palette = {
  bg: "#f1f4ee",
  surface: "#ffffff",
  surfaceAlt: "#e7ede5",
  text: "#13201a",
  muted: "#4d5d55",
  border: "#c9d3c8",
  accent: "#17653a",
  onAccent: "#ffffff",
  accentSoft: "#d9eedf",
  danger: "#a31f1a",
  onDanger: "#ffffff",
  dangerSoft: "#fbe2df",
  warn: "#7a4600",
  warnSoft: "#fdeccb",
  overlay: "rgba(8,16,11,0.72)",
};

const dark: Palette = {
  bg: "#0e1310",
  surface: "#182019",
  surfaceAlt: "#222c24",
  text: "#eef3ee",
  muted: "#a6b4ab",
  border: "#2f3b32",
  accent: "#74d492",
  onAccent: "#062410",
  accentSoft: "#1d3a28",
  danger: "#ff8f86",
  onDanger: "#2a0805",
  dangerSoft: "#3b1f1d",
  warn: "#ffc766",
  warnSoft: "#3a2d10",
  overlay: "rgba(0,0,0,0.72)",
};

export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 } as const;
export const radius = { sm: 8, md: 12, lg: 16, pill: 999 } as const;
export const TOUCH = 48;

export const type = {
  display: { fontSize: 30, fontWeight: "800" as const, letterSpacing: -0.5 },
  title: { fontSize: 26, fontWeight: "700" as const, letterSpacing: -0.3 },
  heading: { fontSize: 18, fontWeight: "600" as const },
  body: { fontSize: 16, fontWeight: "400" as const },
  label: { fontSize: 14, fontWeight: "600" as const },
  caption: { fontSize: 13, fontWeight: "400" as const },
  eyebrow: { fontSize: 12, fontWeight: "700" as const, letterSpacing: 0.8 },
  number: { fontSize: 34, fontWeight: "800" as const, letterSpacing: -0.5 },
};

export function usePalette(): Palette {
  const scheme = useColorScheme();
  // Browser preview only: add ?light to the address to see the light theme whatever the system says.
  if (process.env.EXPO_PUBLIC_DEMO === "1" && String(globalThis.location?.search ?? "").includes("light")) return light;
  return scheme === "dark" ? dark : light;
}
