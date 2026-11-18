import * as WebBrowser from "expo-web-browser";
import React, { useCallback, useEffect, useState } from "react";
import { Linking, View } from "react-native";
import {
  deleteAccount,
  downloadUrl,
  exportStatus,
  loadMethods,
  parseReauthResult,
  reauthMessage,
  requestExport,
  SharedAllotmentsError,
  startReauth,
  type ExportState,
  type Methods,
} from "../src/account/client";
import { useApp } from "../src/state/AppProvider";
import { Banner, Button, Card, Field, Screen, Section, T } from "../src/ui/kit";
import { space } from "../src/ui/theme";
import { SSO_REDIRECT } from "../src/auth/session";

/** The person's own account: a copy of their data, and deleting it (required by the app stores). */
export default function Account() {
  const { session } = useApp();
  const [methods, setMethods] = useState<Methods | null>(null);
  const [exp, setExp] = useState<ExportState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [blocking, setBlocking] = useState<{ id: number; name: string }[]>([]);
  const [deleting, setDeleting] = useState(false);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void loadMethods(session).then(setMethods, (e: Error) => setError(e.message));
  }, [session]);

  // While an export is being built, check on it every couple of seconds.
  useEffect(() => {
    if (exp?.status !== "pending") return;
    const timer = setInterval(() => void exportStatus(session, exp.id).then(setExp, () => undefined), 2000);
    return () => clearInterval(timer);
  }, [exp, session]);

  const askForExport = useCallback(async () => {
    setError(null);
    try {
      setExp(await requestExport(session));
    } catch (e) {
      setError((e as Error).message);
    }
  }, [session]);

  async function remove(proof: { password?: string; reauth_code?: string }) {
    setBusy(true);
    setError(null);
    setBlocking([]);
    try {
      await deleteAccount(session, proof);
      await session.logout(); // the account is gone, so this goes back to the sign-in screen
    } catch (e) {
      if (e instanceof SharedAllotmentsError) setBlocking(e.allotments);
      setError((e as Error).message);
      setBusy(false);
    }
  }

  async function confirmWithProvider(providerId: string) {
    setBusy(true);
    setError(null);
    try {
      const result = await WebBrowser.openAuthSessionAsync(await startReauth(session, providerId), SSO_REDIRECT);
      if (result.type !== "success") return;
      const { code, error: failure } = parseReauthResult(result.url);
      if (!code) {
        setError(reauthMessage(failure ?? "failed"));
        return;
      }
      await remove({ reauth_code: code });
      return;
    } catch (e) {
      setError((e as Error).message);
    }
    setBusy(false);
  }

  const hasPassword = methods?.has_password !== false;
  const canAskAgain = !exp || exp.status === "failed" || exp.status === "expired";

  return (
    <Screen title="Account" subtitle="Your data, and deleting your account.">
      {error ? <Banner tone="danger" text={error} /> : null}

      <Section title="Your data">
        <Card>
          <T>A zip of your account details, everything you added, and the photos and videos you uploaded.</T>
          {exp?.status === "pending" ? <T muted>Preparing your data… this can take a few minutes with a lot of photos.</T> : null}
          {exp?.status === "ready" && exp.url ? (
            <Button label="Open the download" onPress={() => void Linking.openURL(downloadUrl(session, exp.url!))} />
          ) : null}
          {exp?.status === "failed" ? <T tone="danger">The export failed. Please try again.</T> : null}
          {exp?.status === "expired" ? <T muted>That export has expired.</T> : null}
          {canAskAgain ? <Button label="Download my data" kind="secondary" onPress={() => void askForExport()} /> : null}
        </Card>
      </Section>

      <Section title="Delete account">
        <Card tone="danger">
          <T>
            This permanently deletes your account, and any allotment that only you belong to, with its photos. Things you added to
            allotments shared with others stay there, no longer linked to you.
          </T>
          {blocking.map((a) => (
            <T key={a.id} kind="heading">
              {a.name}
            </T>
          ))}
          {!deleting ? (
            <Button label="Delete my account…" kind="danger" onPress={() => setDeleting(true)} />
          ) : hasPassword ? (
            <View style={{ gap: space.md }}>
              <Field label="Your password" secureTextEntry autoCapitalize="none" value={password} onChangeText={setPassword} />
              <Button label="Delete my account for good" kind="danger" busy={busy} disabled={!password} onPress={() => void remove({ password })} />
              <Button label="Cancel" kind="quiet" onPress={() => { setDeleting(false); setPassword(""); }} />
            </View>
          ) : (
            <View style={{ gap: space.md }}>
              <T muted>You have no password, so confirm it is you with a provider.</T>
              {methods?.identities.map((i) => (
                <Button key={i.id} label={`Confirm with ${i.provider_name ?? i.provider}`} kind="danger" busy={busy} onPress={() => void confirmWithProvider(i.provider)} />
              ))}
              <Button label="Cancel" kind="quiet" onPress={() => setDeleting(false)} />
            </View>
          )}
        </Card>
      </Section>

      <Button label="Privacy policy" kind="quiet" onPress={() => void Linking.openURL(`${session.serverUrl}/privacy`)} />
    </Screen>
  );
}
