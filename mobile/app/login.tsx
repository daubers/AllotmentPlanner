import * as WebBrowser from "expo-web-browser";
import React, { useEffect, useState } from "react";
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { APP_VERSION } from "../src/auth/appVersion";
import { checkCompat, type Compat } from "../src/auth/compat";
import { LoginError, normaliseServerUrl, parseSignInResult, signInUrl, ssoMessage, SSO_REDIRECT, type Provider } from "../src/auth/session";
import { useApp } from "../src/state/AppProvider";
import { Banner, Button, Card, Field, T } from "../src/ui/kit";
import { Logo } from "../src/ui/Logo";
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
  const [providers, setProviders] = useState<Provider[]>([]);
  const [compat, setCompat] = useState<Compat | null>(null);

  // Ask the server which single sign-on providers it has, once the address looks complete.
  useEffect(() => {
    let current = true;
    setProviders([]);
    setCompat(null);
    if (!server.trim()) return;
    const wait = setTimeout(
      () =>
        void session.serverInfo(server).then((info) => {
          if (!current) return;
          setProviders(info?.providers ?? []);
          setCompat(checkCompat(info, APP_VERSION));
        }),
      600,
    );
    return () => {
      current = false;
      clearTimeout(wait);
    };
  }, [server, session]);

  async function signInWith(provider: Provider) {
    setBusy(true);
    setError(null);
    try {
      const base = normaliseServerUrl(server);
      const result = await WebBrowser.openAuthSessionAsync(signInUrl(base, provider.id), SSO_REDIRECT);
      if (result.type !== "success") return; // closed without finishing: nothing to report
      const { code, error: failure } = parseSignInResult(result.url);
      if (!code) {
        setError(ssoMessage(failure ?? "failed"));
        return;
      }
      await session.loginWithCode(server, code);
    } catch (err) {
      setError(err instanceof LoginError ? err.message : "Something went wrong signing in");
    } finally {
      setBusy(false);
    }
  }

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
            <Logo size={72} />
            <T kind="display" accessibilityRole="header">
              Allotment
            </T>
            <T muted>Plan, measure and log your plot.</T>
          </View>
          <Card>
            <View style={{ gap: space.lg }}>
              <Field
                label="Server address"
                helper="Where your Allotment server is, e.g. plot.example.com or 192.168.1.5:8000"
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
              {compat ? <Banner tone="warn" text={compat.message} /> : null}
              {error ? <Banner tone="danger" text={error} /> : null}
              <Button label="Sign in" onPress={submit} busy={busy} disabled={!server || !email || !password} />
              {providers.map((p2) => (
                <Button key={p2.id} label={`Sign in with ${p2.name}`} kind="secondary" onPress={() => void signInWith(p2)} disabled={busy} />
              ))}
            </View>
          </Card>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
