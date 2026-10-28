import React, { useState } from "react";
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { LoginError } from "../src/auth/session";
import { useApp } from "../src/state/AppProvider";
import { Banner, Button, Card, Field, T } from "../src/ui/kit";
import { space, usePalette } from "../src/ui/theme";

export default function Login() {
  const { session } = useApp();
  const p = usePalette();
  const [server, setServer] = useState(session.serverUrl);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await session.login(server, email.trim(), password);
    } catch (err) {
      setError(err instanceof LoginError ? err.message : "Something went wrong signing in");
    } finally {
      setBusy(false);
    }
  }

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: p.bg }}>
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={{ padding: space.lg, gap: space.xl, flexGrow: 1, justifyContent: "center" }} keyboardShouldPersistTaps="handled">
          <View style={{ gap: space.xs }}>
            <T kind="display" accessibilityRole="header">
              Allotment
            </T>
            <T muted>Plan, measure and log your plot.</T>
          </View>
          <Card>
            <View style={{ gap: space.lg }}>
              <Field
                label="Server address"
                helper="Where your Allotment server is, e.g. plot.example.com or 192.168.1.5:8080"
                value={server}
                onChangeText={setServer}
                autoCapitalize="none"
                autoCorrect={false}
                keyboardType="url"
                textContentType="URL"
              />
              <Field label="Email" value={email} onChangeText={setEmail} autoCapitalize="none" autoCorrect={false} keyboardType="email-address" textContentType="username" autoComplete="email" />
              <View>
                <Field label="Password" value={password} onChangeText={setPassword} secureTextEntry={!show} textContentType="password" autoComplete="password" onSubmitEditing={submit} returnKeyType="go" />
                <Pressable onPress={() => setShow(!show)} accessibilityRole="button" accessibilityLabel={show ? "Hide password" : "Show password"} style={{ alignSelf: "flex-end", minHeight: 44, justifyContent: "center" }}>
                  <T kind="label" style={{ color: p.accent }}>
                    {show ? "Hide password" : "Show password"}
                  </T>
                </Pressable>
              </View>
              {error ? <Banner tone="danger" text={error} /> : null}
              <Button label="Sign in" onPress={submit} busy={busy} disabled={!server || !email || !password} />
            </View>
          </Card>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
