import React from "react";
import { Switch } from "react-native";
import { usePalette } from "../ui/theme";

/** The "done" switch for a job. Off means still to do. */
export default function JobSwitch({ title, done, disabled, onChange }: { title: string; done: boolean; disabled?: boolean; onChange: (done: boolean) => void }) {
  const p = usePalette();
  return (
    <Switch
      value={done}
      onValueChange={onChange}
      disabled={disabled}
      accessibilityLabel={`${done ? "Put back" : "Mark done"}: ${title}`}
      trackColor={{ false: p.border, true: p.accent }}
      ios_backgroundColor={p.border}
    />
  );
}
