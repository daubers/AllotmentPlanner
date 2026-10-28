import { CameraView, useCameraPermissions } from "expo-camera";
import * as Location from "expo-location";
import { useRouter } from "expo-router";
import { DeviceMotion } from "expo-sensors";
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useApp, useQueueState } from "../src/app/AppProvider";
import {
  MIN_PHOTOS_FOR_MAP,
  SECTORS,
  adviceFor,
  blocked,
  cameraPitchDeg,
  pickHeading,
  summarise,
  verdict,
  type Fix,
  type Shot,
} from "../src/capture/coaching";
import { sessionUploads, type UploadProgress } from "../src/capture/sessionUploads";
import { keepPhoto } from "../src/capture/storage";
import { newId } from "../src/queue/queue";
import { makeStyles, usePalette } from "../src/ui/theme";

export default function Capture() {
  const { queue, allotmentId, api } = useApp();
  const router = useRouter();
  const palette = usePalette();
  const s = useMemo(() => makeStyles(palette), [palette]);
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
      <SafeAreaView style={s.screen}>
        <ActivityIndicator style={{ marginTop: 40 }} />
      </SafeAreaView>
    );
  }
  if (!camera.granted || !locationOk) {
    return (
      <SafeAreaView style={s.screen}>
        <View style={s.content}>
          <Text style={s.title}>Camera and location</Text>
          <Text style={s.text}>
            Photos are only useful for the map if they know where they were taken, so this needs the camera and your precise location.
          </Text>
          {!camera.granted ? (
            <Pressable style={s.button} onPress={askCamera}>
              <Text style={s.buttonText}>Allow camera</Text>
            </Pressable>
          ) : null}
          {!locationOk ? <Text style={s.error}>Location is off. Turn it on for Allotment in your phone's settings.</Text> : null}
          <Pressable style={s.ghost} onPress={() => router.back()}>
            <Text style={s.ghostText}>Back</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  if (finished) {
    const ready = uploads.waiting === 0 && uploads.failed === 0 && summary.photos >= MIN_PHOTOS_FOR_MAP;
    return (
      <SafeAreaView style={s.screen}>
        <ScrollView contentContainerStyle={s.content}>
          <Text style={s.title}>Walk finished</Text>
          <View style={s.card}>
            <Text style={s.heading}>
              {summary.photos} photos · {Math.round(summary.walkedM)} m walked · {summary.sectors} of {SECTORS} directions
            </Text>
            {verdict(summary).map((note) => (
              <Text key={note} style={s.text}>
                {note}
              </Text>
            ))}
          </View>
          <View style={s.card}>
            <Text style={s.heading}>Upload</Text>
            <Text style={s.text}>
              {uploads.waiting === 0 && uploads.failed === 0
                ? "All photos are on the server."
                : `${uploads.waiting} of ${uploads.total} still to send${queueState.active ? ` (${Math.round(queueState.active.progress * 100)}% of the current one)` : ""}`}
            </Text>
            {uploads.failed ? <Text style={s.error}>{uploads.failed} failed. See the home screen to retry.</Text> : null}
          </View>
          {mapMessage ? <Text style={s.text}>{mapMessage}</Text> : null}
          <Pressable style={[s.button, { opacity: ready ? 1 : 0.5 }]} disabled={!ready} onPress={buildMap}>
            <Text style={s.buttonText}>Build a map from this walk</Text>
          </Pressable>
          {!ready && summary.photos >= MIN_PHOTOS_FOR_MAP ? <Text style={s.muted}>Available once every photo has been sent.</Text> : null}
          <Pressable style={s.ghost} onPress={() => setFinished(false)}>
            <Text style={s.ghostText}>Keep taking photos</Text>
          </Pressable>
          <Pressable style={s.ghost} onPress={another}>
            <Text style={s.ghostText}>Start a new walk</Text>
          </Pressable>
          <Pressable style={s.ghost} onPress={() => router.back()}>
            <Text style={s.ghostText}>Done</Text>
          </Pressable>
        </ScrollView>
      </SafeAreaView>
    );
  }

  const accuracy = fix?.accuracy != null ? `±${Math.round(fix.accuracy)} m` : "no fix";
  return (
    <View style={{ flex: 1, backgroundColor: "#000" }}>
      <CameraView ref={cameraRef} style={{ flex: 1 }} facing="back" />
      <SafeAreaView style={{ position: "absolute", top: 0, left: 0, right: 0, padding: 12, gap: 6 }} pointerEvents="none">
        <Text style={{ color: "#fff", fontSize: 14, backgroundColor: "#0008", padding: 6, borderRadius: 6 }}>
          GPS {accuracy} · {heading === null ? "no compass" : `${Math.round(heading)}°`} · {summary.photos} photos · {Math.round(summary.walkedM)} m
        </Text>
        {advice.map((a) => (
          <Text
            key={a.id}
            style={{ color: "#fff", fontSize: 15, padding: 8, borderRadius: 6, backgroundColor: a.level === "block" ? "#b3261ecc" : "#8a5a00cc" }}
          >
            {a.text}
          </Text>
        ))}
        {shots.length === 0 && advice.length === 0 ? (
          <Text style={{ color: "#fff", fontSize: 15, backgroundColor: "#0008", padding: 8, borderRadius: 6 }}>
            Walk the edge of the plot. Face inwards, keep the fence in view, and take a photo every few steps.
          </Text>
        ) : null}
      </SafeAreaView>
      <SafeAreaView style={{ position: "absolute", bottom: 0, left: 0, right: 0 }}>
        <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-around", padding: 16 }}>
          <Pressable style={[s.ghost, { backgroundColor: "#0008", borderColor: "#fff6" }]} onPress={() => router.back()}>
            <Text style={{ color: "#fff", fontSize: 16 }}>Close</Text>
          </Pressable>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Take photo"
            disabled={stopped}
            onPress={shoot}
            style={{
              width: 76,
              height: 76,
              borderRadius: 38,
              borderWidth: 5,
              borderColor: "#fff",
              backgroundColor: stopped ? "#888" : "#fff",
              opacity: stopped ? 0.5 : 1,
            }}
          />
          <Pressable
            style={[s.ghost, { backgroundColor: "#0008", borderColor: "#fff6", opacity: shots.length ? 1 : 0.4 }]}
            disabled={!shots.length}
            onPress={() => setFinished(true)}
          >
            <Text style={{ color: "#fff", fontSize: 16 }}>Finish</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    </View>
  );
}
