import "../src/dev/demo";
import { Redirect, Stack, useSegments } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { DemoFrame } from "../src/dev/DemoFrame";
import { AppProvider, useApp } from "../src/state/AppProvider";
import { DialogHost } from "../src/ui/dialog";

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
      <Stack.Screen name="seeds/index" />
      <Stack.Screen name="seeds/[id]" />
      <Stack.Screen name="trays/index" />
      <Stack.Screen name="trays/[id]" />
      <Stack.Screen name="found/index" />
      <Stack.Screen name="found/[id]" />
      <Stack.Screen name="tasks/index" />
      <Stack.Screen name="tasks/new" />
      <Stack.Screen name="tasks/[id]" />
      <Stack.Screen name="beds/index" />
      <Stack.Screen name="beds/[id]" />
      <Stack.Screen name="photo" options={{ animation: "slide_from_bottom" }} />
      <Stack.Screen name="demo" />
      <Stack.Screen name="capture" options={{ animation: "slide_from_bottom" }} />
    </Stack>
  );
}

export default function RootLayout() {
  return (
    <AppProvider>
      <StatusBar style="auto" />
      <DialogHost />
      <DemoFrame>
        <Gate />
      </DemoFrame>
    </AppProvider>
  );
}
