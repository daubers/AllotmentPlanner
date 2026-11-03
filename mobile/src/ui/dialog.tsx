import React, { useEffect, useState } from "react";
import { Modal, Pressable, View } from "react-native";
import { Button, T } from "./kit";
import { radius, space, usePalette } from "./theme";

export type DialogAction = { label: string; kind?: "primary" | "secondary" | "quiet"; onPress?: () => void };
export type DialogSpec = { title: string; message?: string; actions: DialogAction[]; /** Run if the dialog is dismissed (Android back, tap outside). */ onDismiss?: () => void };

// A tiny store so any code can ask a question: `showDialog({...})`. The host below draws it in the app's own
// theme. The system alert would not do: on some builds it ignores the dark theme the rest of the app follows.
let current: DialogSpec | null = null;
const listeners = new Set<() => void>();
const set = (spec: DialogSpec | null) => {
  current = spec;
  listeners.forEach((l) => l());
};

export const showDialog = (spec: DialogSpec) => set(spec);

/** Mount once, near the root. */
export function DialogHost() {
  const p = usePalette();
  const [, tick] = useState(0);
  useEffect(() => {
    const l = () => tick((n) => n + 1);
    listeners.add(l);
    return () => void listeners.delete(l);
  }, []);
  const spec = current;
  const close = (after?: () => void) => {
    set(null);
    after?.();
  };
  return (
    <Modal visible={spec !== null} transparent animationType="fade" onRequestClose={() => close(spec?.onDismiss)} statusBarTranslucent>
      <Pressable
        accessibilityLabel="Close"
        onPress={() => close(spec?.onDismiss)}
        style={{ flex: 1, backgroundColor: "rgba(0,0,0,0.5)", justifyContent: "center", padding: space.xl }}
      >
        {/* Swallow taps on the card so they do not dismiss. */}
        <Pressable
          accessible={false}
          style={{ backgroundColor: p.surface, borderRadius: radius.lg, padding: space.lg, gap: space.md, borderWidth: 1, borderColor: p.border }}
        >
          <T kind="heading" accessibilityRole="header">
            {spec?.title ?? ""}
          </T>
          {spec?.message ? <T muted>{spec.message}</T> : null}
          <View style={{ gap: space.sm, marginTop: space.xs }}>
            {spec?.actions.map((a) => (
              <Button key={a.label} label={a.label} kind={a.kind ?? "secondary"} onPress={() => close(a.onPress)} />
            ))}
          </View>
        </Pressable>
      </Pressable>
    </Modal>
  );
}
