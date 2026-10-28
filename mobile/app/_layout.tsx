import "../src/dev/demo";
import { Redirect, Stack, useSegments } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { DemoFrame } from "../src/dev/DemoFrame";
import { AppProvider, useApp } from "../src/state/AppProvider";

function Gate() {
  const { signedIn } = useApp();
  const onLogin = useSegments()[0] === "login";
  if (!signedIn && !onLogin) return <Redirect href="/login" />;
  if (signedIn && onLogin) return <Redirect href="/" />;
  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="index" />
      <Stack.Screen name="login" />
      <Stack.Screen name="uploads" />
      <Stack.Screen name="measure/index" />
      <Stack.Screen name="measure/[id]" />
      <Stack.Screen name="measure/apply" />
      <Stack.Screen name="demo" />
      <Stack.Screen name="capture" options={{ animation: "slide_from_bottom" }} />
    </Stack>
  );
}

export default function RootLayout() {
  return (
    <AppProvider>
      <StatusBar style="auto" />
      <DemoFrame>
        <Gate />
      </DemoFrame>
    </AppProvider>
  );
}
