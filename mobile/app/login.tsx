import React, { useMemo, useState } from "react";
import { ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useApp } from "../src/state/AppProvider";
import { LoginError } from "../src/auth/session";
import { makeStyles, usePalette } from "../src/ui/theme";

export default function Login() {
  const { session } = useApp();
  const palette = usePalette();
  const s = useMemo(() => makeStyles(palette), [palette]);
  const [server, setServer] = useState(session.serverUrl);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
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
    <SafeAreaView style={s.screen}>
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={s.content} keyboardShouldPersistTaps="handled">
          <Text style={s.title}>Allotment</Text>
          <View style={s.card}>
            <Text style={s.muted}>Server address</Text>
            <TextInput
              style={s.input}
              value={server}
              onChangeText={setServer}
              placeholder="plot.example.com or 192.168.1.5:8080"
              placeholderTextColor={palette.muted}
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="url"
              accessibilityLabel="Server address"
            />
            <Text style={s.muted}>Email</Text>
            <TextInput
              style={s.input}
              value={email}
              onChangeText={setEmail}
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="email-address"
              textContentType="username"
              accessibilityLabel="Email"
            />
            <Text style={s.muted}>Password</Text>
            <TextInput
              style={s.input}
              value={password}
              onChangeText={setPassword}
              secureTextEntry
              textContentType="password"
              accessibilityLabel="Password"
              onSubmitEditing={submit}
            />
            {error ? <Text style={s.error}>{error}</Text> : null}
            <Pressable style={s.button} onPress={submit} disabled={busy || !server || !email || !password} accessibilityRole="button">
              {busy ? <ActivityIndicator color="#fff" /> : <Text style={s.buttonText}>Sign in</Text>}
            </Pressable>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
