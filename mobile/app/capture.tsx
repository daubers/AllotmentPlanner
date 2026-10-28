import { CameraView, useCameraPermissions } from "expo-camera";
import * as Location from "expo-location";
import { useRouter } from "expo-router";
import { DeviceMotion } from "expo-sensors";
import React, { useCallback, useEffect, useRef, useState } from "react";
import { Pressable, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useApp, useQueueState } from "../src/state/AppProvider";
import {
  MIN_PHOTOS_FOR_MAP,
  adviceFor,
  blocked,
  cameraPitchDeg,
  pickHeading,
  summarise,
  type Fix,
  type Shot,
} from "../src/capture/coaching";
import { sessionUploads, type UploadProgress } from "../src/capture/sessionUploads";
import { keepPhoto } from "../src/capture/storage";
import { newId } from "../src/queue/queue";
import { CaptureSummary, Hud, Pill } from "../src/capture/ui";
import { Banner, Button, Card, Loading, Screen, T, type Tone } from "../src/ui/kit";
import { radius, space, usePalette } from "../src/ui/theme";

export default function Capture() {
  const { queue, allotmentId, api } = useApp();
  const router = useRouter();
  const palette = usePalette();
  const queueState = useQueueState();

  const [camera, askCamera] = useCameraPermissions();
  const [locationOk, setLocationOk] = useState<boolean | null>(null);
  const cameraRef = useRef<CameraView>(null);

  const [sessionId, setSessionId] = useState(() => newId());
  const [fix, setFix] = useState<Fix | null>(null);
  const [heading, setHeading] = useState<number | null>(null);
  const [pitch, setPitch] = useState<number | null>(null);
  const [shots, setShots] = useState<Shot[]>([]);
  const [now, setNow] = useState(Date.now());
  const [busy, setBusy] = useState(false);
  const [finished, setFinished] = useState(false);
  const [uploads, setUploads] = useState<UploadProgress>({ total: 0, waiting: 0, failed: 0 });
  const [mapMessage, setMapMessage] = useState<string | null>(null);

  // Ask for location, then follow position, compass and tilt while this screen is open.
  useEffect(() => {
    let cancelled = false;
    const subs: { remove: () => void }[] = [];
    (async () => {
      const { granted } = await Location.requestForegroundPermissionsAsync();
      if (cancelled) return;
      setLocationOk(granted);
      if (!granted) return;
      subs.push(
        await Location.watchPositionAsync(
          { accuracy: Location.Accuracy.BestForNavigation, timeInterval: 1000, distanceInterval: 0 },
          (loc) =>
            setFix({
              lat: loc.coords.latitude,
              lng: loc.coords.longitude,
              accuracy: loc.coords.accuracy,
              timestamp: loc.timestamp,
            }),
        ),
      );
      subs.push(await Location.watchHeadingAsync((h) => setHeading(pickHeading(h.trueHeading, h.magHeading))));
      DeviceMotion.setUpdateInterval(250);
      subs.push(DeviceMotion.addListener((m) => m.rotation && setPitch(cameraPitchDeg(m.rotation.beta))));
    })().catch(() => setLocationOk(false));
    const tick = setInterval(() => setNow(Date.now()), 1000);
    return () => {
      cancelled = true;
      subs.forEach((sub) => sub.remove());
      clearInterval(tick);
    };
  }, []);

  const refreshUploads = useCallback(async () => {
    setUploads(sessionUploads(await queue.jobs(), sessionId));
  }, [queue, sessionId]);
  useEffect(() => {
    void refreshUploads();
  }, [refreshUploads, queueState.pending, queueState.failed, shots.length]);

  const last = shots.length ? shots[shots.length - 1] : null;
  const advice = adviceFor({ fix, heading, pitchDeg: pitch, last, now });
  const stopped = blocked(advice) || busy || allotmentId === null;
  const summary = summarise(shots);

  async function shoot() {
    if (!cameraRef.current || !fix || allotmentId === null) return;
    setBusy(true);
    try {
      const at = Date.now();
      const taken = { ...fix };
      const photo = await cameraRef.current.takePictureAsync({ quality: 0.9 });
      const clientId = `${sessionId}-${shots.length + 1}`;
      const uri = await keepPhoto(photo.uri, clientId);
      const fields: Record<string, string> = {
        lat: String(taken.lat),
        lng: String(taken.lng),
        taken_at: new Date(at).toISOString(),
        capture_session: sessionId,
        client_id: clientId,
      };
      if (heading !== null) fields.heading = heading.toFixed(1);
      await queue.enqueue(
        "upload",
        { allotmentId, uri, name: `${clientId}.jpg`, mimeType: "image/jpeg", fields, deleteAfterUpload: true },
        clientId,
      );
      setShots((prev) => [...prev, { lat: taken.lat, lng: taken.lng, accuracy: taken.accuracy, heading, takenAt: at }]);
      void queue.run();
    } finally {
      setBusy(false);
    }
  }

  async function buildMap() {
    if (allotmentId === null) return;
    setMapMessage("Starting…");
    const { data, error } = await api.POST("/api/v1/allotments/{allotment_id}/map-jobs", {
      params: { path: { allotment_id: allotmentId } },
      body: {
        name: `Walk ${new Date().toLocaleDateString()}`,
        capture_session: sessionId,
        detect_objects: true,
        overlay: false,
        view: "oblique",
        camera_height_m: 1.5,
      },
    });
    if (data) setMapMessage("Building your map. It appears in the web app under Layers when it is done.");
    else setMapMessage((error as { message?: string } | undefined)?.message ?? "Couldn't start the map");
  }

  function another() {
    setSessionId(newId());
    setShots([]);
    setFinished(false);
    setMapMessage(null);
  }

  if (!camera || locationOk === null) {
    return (
      <Screen title="Photograph the plot">
        <Loading label="Getting the camera ready…" />
      </Screen>
    );
  }
  if (!camera.granted || !locationOk) {
    return (
      <Screen title="Camera and location" subtitle="Photos only help the map if they know where they were taken.">
        <Card>
          <T>Allotment needs the camera, and your precise location, to record where each photo was taken.</T>
          {!camera.granted ? <Button label="Allow the camera" onPress={askCamera} /> : <T tone="ok" kind="label">Camera allowed</T>}
          {!locationOk ? <Banner tone="danger" text="Location is off. Turn it on for Allotment in your phone's settings, then come back." /> : <T tone="ok" kind="label">Location allowed</T>}
        </Card>
      </Screen>
    );
  }

  if (finished) {
    return (
      <CaptureSummary
        summary={summary}
        uploads={uploads}
        queueState={queueState}
        mapMessage={mapMessage}
        minPhotos={MIN_PHOTOS_FOR_MAP}
        onBuild={buildMap}
        onKeepGoing={() => setFinished(false)}
        onNewWalk={another}
        onDone={() => router.back()}
        onReview={() => router.push("/uploads")}
      />
    );
  }

  const gpsTone: Tone = !fix || now - fix.timestamp > 10_000 ? "danger" : fix.accuracy !== null && fix.accuracy > 15 ? "warn" : "ok";
  const gps = fix?.accuracy != null ? `±${Math.round(fix.accuracy)} m` : "searching";
  const compassTone: Tone = heading === null ? "warn" : "ok";
  const levelTone: Tone = pitch === null ? "neutral" : Math.abs(pitch) > 25 ? "warn" : "ok";
  const levelText = pitch === null ? "no sensor" : Math.abs(pitch) > 25 ? (pitch > 0 ? "too high" : "too low") : "level";
  const top = advice[0];

  return (
    <View style={{ flex: 1, backgroundColor: "#000" }}>
      <CameraView ref={cameraRef} style={{ flex: 1 }} facing="back" />
      <SafeAreaView style={{ position: "absolute", top: 0, left: 0, right: 0, padding: space.md, gap: space.sm }} pointerEvents="box-none">
        <View style={{ flexDirection: "row", gap: space.sm }} accessibilityRole="summary">
          <Hud label="GPS" value={gps} tone={gpsTone} />
          <Hud label="Compass" value={heading === null ? "none" : `${Math.round(heading)}°`} tone={compassTone} />
          <Hud label="Camera" value={levelText} tone={levelTone} />
        </View>
        {top ? (
          <Banner tone={top.level === "block" ? "danger" : "warn"} text={top.text} />
        ) : shots.length === 0 ? (
          <View style={{ backgroundColor: palette.overlay, borderRadius: radius.md, padding: space.md }}>
            <T style={{ color: "#fff" }}>Walk the edge of the plot. Face inwards with the fence in view, and take a photo every few steps.</T>
          </View>
        ) : null}
      </SafeAreaView>
      <SafeAreaView style={{ position: "absolute", bottom: 0, left: 0, right: 0 }} pointerEvents="box-none">
        <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", padding: space.lg }}>
          <View style={{ flex: 1, alignItems: "flex-start" }}>
            <Pill label="Close" onPress={() => router.back()} />
          </View>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Take photo"
            accessibilityState={{ disabled: stopped }}
            disabled={stopped}
            onPress={shoot}
            style={{ width: 80, height: 80, borderRadius: 40, borderWidth: 5, borderColor: "#fff", alignItems: "center", justifyContent: "center", opacity: stopped ? 0.4 : 1 }}
          >
            <View style={{ width: 58, height: 58, borderRadius: 29, backgroundColor: "#fff" }} />
          </Pressable>
          <View style={{ flex: 1, alignItems: "flex-end" }}>
            <Pill label={shots.length ? `Finish · ${shots.length}` : "Finish"} onPress={() => setFinished(true)} disabled={!shots.length} />
          </View>
        </View>
      </SafeAreaView>
    </View>
  );
}
