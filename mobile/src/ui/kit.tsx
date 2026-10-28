import { useRouter } from "expo-router";
import React, { useMemo } from "react";
import { ActivityIndicator, Pressable, ScrollView, Text, TextInput, View, type TextInputProps } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { makeStyles, usePalette } from "./theme";

export function useStyles() {
  const palette = usePalette();
  return { palette, s: useMemo(() => makeStyles(palette), [palette]) };
}

/** A scrolling screen with a back button and title, inside the safe area. */
export function Screen({
  title,
  back = true,
  children,
  footer,
}: {
  title: string;
  back?: boolean;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  const { s } = useStyles();
  const router = useRouter();
  return (
    <SafeAreaView style={s.screen}>
      <View style={[s.row, { paddingHorizontal: 16, paddingTop: 8 }]}>
        {back ? (
          <Pressable onPress={() => router.back()} accessibilityRole="button" accessibilityLabel="Back" hitSlop={12}>
            <Text style={[s.text, { fontSize: 17 }]}>‹ Back</Text>
          </Pressable>
        ) : (
          <View />
        )}
      </View>
      <ScrollView contentContainerStyle={s.content} keyboardShouldPersistTaps="handled">
        <Text style={s.title} accessibilityRole="header">
          {title}
        </Text>
        {children}
      </ScrollView>
      {footer ? <View style={[s.footer]}>{footer}</View> : null}
    </SafeAreaView>
  );
}

export function Card({ children }: { children: React.ReactNode }) {
  const { s } = useStyles();
  return <View style={s.card}>{children}</View>;
}

export function Button({
  label,
  onPress,
  kind = "primary",
  disabled,
  busy,
}: {
  label: string;
  onPress: () => void;
  kind?: "primary" | "secondary";
  disabled?: boolean;
  busy?: boolean;
}) {
  const { s } = useStyles();
  const primary = kind === "primary";
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: !!disabled || !!busy, busy: !!busy }}
      disabled={disabled || busy}
      onPress={onPress}
      style={[primary ? s.button : s.ghost, (disabled || busy) && { opacity: 0.5 }]}
    >
      {busy ? <ActivityIndicator color={primary ? "#fff" : undefined} /> : <Text style={primary ? s.buttonText : s.ghostText}>{label}</Text>}
    </Pressable>
  );
}

export function ProgressBar({ value, total }: { value: number; total: number }) {
  const { palette } = useStyles();
  const fraction = total > 0 ? Math.min(1, value / total) : 0;
  return (
    <View
      accessibilityRole="progressbar"
      accessibilityValue={{ min: 0, max: total, now: value }}
      style={{ height: 8, borderRadius: 4, backgroundColor: palette.border, overflow: "hidden" }}
    >
      <View style={{ width: `${fraction * 100}%`, height: 8, backgroundColor: palette.accent }} />
    </View>
  );
}

export function Field({ label, ...props }: { label: string } & TextInputProps) {
  const { s, palette } = useStyles();
  return (
    <View style={{ gap: 4 }}>
      <Text style={s.muted}>{label}</Text>
      <TextInput style={s.input} placeholderTextColor={palette.muted} accessibilityLabel={label} {...props} />
    </View>
  );
}
