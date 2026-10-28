import { useRouter } from "expo-router";
import React from "react";
import {
  ActivityIndicator,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  type StyleProp,
  type TextInputProps,
  type ViewStyle,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { TOUCH, radius, space, type, usePalette, type Palette } from "./theme";

export function useStyles() {
  return { palette: usePalette() };
}

export type Tone = "neutral" | "ok" | "warn" | "danger";

export function toneColors(p: Palette, tone: Tone): { fg: string; bg: string } {
  switch (tone) {
    case "ok":
      return { fg: p.accent, bg: p.accentSoft };
    case "warn":
      return { fg: p.warn, bg: p.warnSoft };
    case "danger":
      return { fg: p.danger, bg: p.dangerSoft };
    default:
      return { fg: p.muted, bg: p.surfaceAlt };
  }
}

/** Plain text in the app's styles. */
export function T({
  kind = "body",
  muted,
  tone,
  style,
  children,
  ...rest
}: {
  kind?: keyof typeof type;
  muted?: boolean;
  tone?: Tone;
  style?: StyleProp<any>;
  children: React.ReactNode;
} & React.ComponentProps<typeof Text>) {
  const p = usePalette();
  const color = tone ? toneColors(p, tone).fg : muted ? p.muted : p.text;
  return (
    <Text {...rest} style={[type[kind], { color }, style]}>
      {children}
    </Text>
  );
}

/** A screen: back button, large title (and optional subtitle), scrolling body, optional pinned footer. */
export function Screen({
  title,
  subtitle,
  back = true,
  backLabel = "Back",
  right,
  children,
  footer,
  scroll = true,
}: {
  title?: string;
  subtitle?: string;
  back?: boolean;
  backLabel?: string;
  right?: React.ReactNode;
  children: React.ReactNode;
  footer?: React.ReactNode;
  scroll?: boolean;
}) {
  const p = usePalette();
  const router = useRouter();
  const header = (
    <>
      {back || right ? (
        <View style={styles.topBar}>
          {back ? (
            <Pressable
              onPress={() => router.back()}
              accessibilityRole="button"
              accessibilityLabel={backLabel}
              hitSlop={8}
              style={styles.back}
            >
              <T kind="heading" style={{ color: p.accent }}>
                ‹
              </T>
              <T kind="body" style={{ color: p.accent, fontWeight: "600" }}>
                {backLabel}
              </T>
            </Pressable>
          ) : (
            <View />
          )}
          {right}
        </View>
      ) : null}
      {title ? (
        <View style={{ gap: space.xs }}>
          <T kind="title" accessibilityRole="header">
            {title}
          </T>
          {subtitle ? <T muted>{subtitle}</T> : null}
        </View>
      ) : null}
    </>
  );
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: p.bg }}>
      {scroll ? (
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          {header}
          {children}
        </ScrollView>
      ) : (
        <View style={styles.content}>
          {header}
          {children}
        </View>
      )}
      {footer ? (
        <View style={[styles.footer, { backgroundColor: p.bg, borderTopColor: p.border }]}>{footer}</View>
      ) : null}
    </SafeAreaView>
  );
}

export function Card({ children, style, tone }: { children: React.ReactNode; style?: StyleProp<ViewStyle>; tone?: Tone }) {
  const p = usePalette();
  const t = tone && tone !== "neutral" ? toneColors(p, tone) : null;
  return (
    <View
      style={[
        styles.card,
        { backgroundColor: t ? t.bg : p.surface, borderColor: t ? t.fg : p.border },
        style,
      ]}
    >
      {children}
    </View>
  );
}

/** A small heading above a group. */
export function Section({ title, right, children }: { title: string; right?: React.ReactNode; children: React.ReactNode }) {
  return (
    <View style={{ gap: space.sm }}>
      <View style={styles.sectionHead}>
        <T kind="eyebrow" muted accessibilityRole="header">
          {title.toUpperCase()}
        </T>
        {right}
      </View>
      {children}
    </View>
  );
}

/** A tappable row inside a card: title, optional second line, optional value, chevron. */
export function Row({
  title,
  subtitle,
  value,
  valueTone,
  onPress,
  first,
  dim,
  accessibilityLabel,
}: {
  title: string;
  subtitle?: string;
  value?: string;
  valueTone?: Tone;
  onPress?: () => void;
  first?: boolean;
  dim?: boolean;
  accessibilityLabel?: string;
}) {
  const p = usePalette();
  const Wrapper: any = onPress ? Pressable : View;
  return (
    <Wrapper
      onPress={onPress}
      accessibilityRole={onPress ? "button" : undefined}
      accessibilityLabel={accessibilityLabel}
      style={({ pressed }: { pressed?: boolean }) => [
        styles.row,
        { borderTopColor: p.border, borderTopWidth: first ? 0 : StyleSheet.hairlineWidth, opacity: dim ? 0.55 : 1, backgroundColor: pressed ? p.surfaceAlt : "transparent" },
      ]}
    >
      <View style={{ flex: 1, gap: 2 }}>
        <T kind="body" style={{ fontWeight: "500" }}>
          {title}
        </T>
        {subtitle ? <T kind="caption" muted>{subtitle}</T> : null}
      </View>
      {value ? (
        <T kind="body" tone={valueTone ?? "neutral"} style={{ fontWeight: "700" }}>
          {value}
        </T>
      ) : null}
      {onPress ? (
        <T kind="heading" muted style={{ marginLeft: space.xs }}>
          ›
        </T>
      ) : null}
    </Wrapper>
  );
}

export function Button({
  label,
  onPress,
  kind = "primary",
  disabled,
  busy,
  small,
}: {
  label: string;
  onPress: () => void;
  kind?: "primary" | "secondary" | "quiet" | "danger";
  disabled?: boolean;
  busy?: boolean;
  small?: boolean;
}) {
  const p = usePalette();
  const colors = {
    primary: { bg: p.accent, fg: p.onAccent, border: p.accent },
    secondary: { bg: "transparent", fg: p.text, border: p.border },
    quiet: { bg: "transparent", fg: p.accent, border: "transparent" },
    danger: { bg: p.danger, fg: p.onDanger, border: p.danger },
  }[kind];
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: !!disabled || !!busy, busy: !!busy }}
      disabled={disabled || busy}
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        { backgroundColor: colors.bg, borderColor: colors.border, minHeight: small ? 40 : TOUCH, opacity: disabled ? 0.45 : pressed ? 0.85 : 1 },
      ]}
    >
      {busy ? <ActivityIndicator color={colors.fg} /> : <T kind="heading" style={{ color: colors.fg, fontSize: small ? 15 : 17 }}>{label}</T>}
    </Pressable>
  );
}

export function Chip({ label, tone = "neutral" }: { label: string; tone?: Tone }) {
  const p = usePalette();
  const c = toneColors(p, tone);
  return (
    <View style={[styles.chip, { backgroundColor: c.bg }]}>
      <T kind="label" style={{ color: c.fg }}>
        {label}
      </T>
    </View>
  );
}

export function ProgressBar({ value, total, tone = "ok" }: { value: number; total: number; tone?: Tone }) {
  const p = usePalette();
  const fraction = total > 0 ? Math.min(1, value / total) : 0;
  return (
    <View
      accessibilityRole="progressbar"
      accessibilityValue={{ min: 0, max: total, now: value }}
      style={{ height: 10, borderRadius: 5, backgroundColor: p.surfaceAlt, overflow: "hidden" }}
    >
      <View style={{ width: `${fraction * 100}%`, height: 10, backgroundColor: toneColors(p, tone).fg }} />
    </View>
  );
}

/** A banner for status that needs attention, with an optional action. */
export function Banner({ tone, text, action, onAction }: { tone: Tone; text: string; action?: string; onAction?: () => void }) {
  const p = usePalette();
  const c = toneColors(p, tone);
  return (
    <View accessibilityRole="alert" style={[styles.banner, { backgroundColor: c.bg, borderColor: c.fg }]}>
      <T kind="body" style={{ color: c.fg, flex: 1, fontWeight: "600" }}>
        {text}
      </T>
      {action && onAction ? (
        <Pressable onPress={onAction} accessibilityRole="button" hitSlop={8} style={{ minHeight: 32, justifyContent: "center" }}>
          <T kind="label" style={{ color: c.fg, textDecorationLine: "underline" }}>
            {action}
          </T>
        </Pressable>
      ) : null}
    </View>
  );
}

export function Field({
  label,
  helper,
  error,
  suffix,
  large,
  ...props
}: { label: string; helper?: string; error?: string; suffix?: string; large?: boolean } & TextInputProps) {
  const p = usePalette();
  return (
    <View style={{ gap: space.xs }}>
      <T kind="label">{label}</T>
      <View style={[styles.inputWrap, { backgroundColor: p.surface, borderColor: error ? p.danger : p.border, minHeight: large ? 64 : TOUCH }]}>
        <TextInput
          style={[{ flex: 1, color: p.text, fontSize: large ? 28 : 17, fontWeight: large ? "700" : "400", paddingVertical: 8 }, Platform.select({ web: { outlineStyle: "none" } as object, default: {} })]}
          placeholderTextColor={p.muted}
          accessibilityLabel={label}
          {...props}
        />
        {suffix ? <T kind="body" muted>{suffix}</T> : null}
      </View>
      {error ? (
        <T kind="caption" tone="danger" accessibilityRole="alert">
          {error}
        </T>
      ) : helper ? (
        <T kind="caption" muted>
          {helper}
        </T>
      ) : null}
    </View>
  );
}

export function Segmented<V extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: V; label: string }[];
  value: V;
  onChange: (v: V) => void;
}) {
  const p = usePalette();
  return (
    <View style={[styles.segmented, { backgroundColor: p.surfaceAlt }]} accessibilityRole="radiogroup">
      {options.map((o) => {
        const on = o.value === value;
        return (
          <Pressable
            key={o.value}
            onPress={() => onChange(o.value)}
            accessibilityRole="radio"
            accessibilityState={{ selected: on }}
            style={[styles.segment, on && { backgroundColor: p.surface, borderColor: p.border, borderWidth: 1 }]}
          >
            <T kind="label" style={{ color: on ? p.text : p.muted }}>
              {o.label}
            </T>
          </Pressable>
        );
      })}
    </View>
  );
}

export function Empty({ title, body, action }: { title: string; body: string; action?: React.ReactNode }) {
  return (
    <Card>
      <T kind="heading">{title}</T>
      <T muted>{body}</T>
      {action}
    </Card>
  );
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  const p = usePalette();
  return (
    <View style={{ alignItems: "center", gap: space.sm, paddingVertical: space.xl }} accessibilityLiveRegion="polite">
      <ActivityIndicator color={p.accent} />
      <T muted>{label}</T>
    </View>
  );
}

const styles = StyleSheet.create({
  content: { padding: space.lg, gap: space.lg, paddingBottom: space.xxl },
  topBar: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", minHeight: 44 },
  back: { flexDirection: "row", alignItems: "center", gap: 4, minHeight: 44, paddingRight: space.md },
  footer: { padding: space.lg, gap: space.sm, borderTopWidth: StyleSheet.hairlineWidth },
  card: { borderRadius: radius.lg, borderWidth: 1, padding: space.lg, gap: space.sm },
  sectionHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", minHeight: 24 },
  row: { flexDirection: "row", alignItems: "center", gap: space.sm, minHeight: 56, paddingVertical: space.sm },
  button: { borderRadius: radius.md, borderWidth: 1, alignItems: "center", justifyContent: "center", paddingHorizontal: space.lg },
  chip: { borderRadius: radius.pill, paddingHorizontal: 10, paddingVertical: 4, alignSelf: "flex-start" },
  banner: { flexDirection: "row", alignItems: "center", gap: space.md, borderRadius: radius.md, borderWidth: 1, padding: space.md, minHeight: 48 },
  inputWrap: { flexDirection: "row", alignItems: "center", gap: space.sm, borderRadius: radius.md, borderWidth: 1, paddingHorizontal: space.md },
  segmented: { flexDirection: "row", borderRadius: radius.md, padding: 3 },
  segment: { flex: 1, minHeight: 40, alignItems: "center", justifyContent: "center", borderRadius: radius.sm },
});
