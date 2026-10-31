import { CameraView, useCameraPermissions } from "expo-camera";
import { useLocalSearchParams, useRouter } from "expo-router";
import React, { useRef, useState } from "react";
import { View } from "react-native";
import { keepPhoto } from "../src/capture/storage";
import { newId } from "../src/queue/queue";
import { photoFields, scanFields } from "../src/seeds/model";
import { useApp } from "../src/state/AppProvider";
import { Banner, Button, Screen, T } from "../src/ui/kit";
import { space } from "../src/ui/theme";

/** One camera screen for every kind of photo that is not a map walk: the back of a packet (read into
 *  a draft), or a photo of a packet, tray or planting. The photo is queued and sent when there is signal. */
export default function Photo() {
  const { queue, allotmentId } = useApp();
  const router = useRouter();
  const params = useLocalSearchParams<{ mode?: string; packetId?: string; trayId?: string; plantingId?: string; taskId?: string }>();
  const [permission, ask] = useCameraPermissions();
  const camera = useRef<CameraView>(null);
  const [taken, setTaken] = useState(0);
  const [busy, setBusy] = useState(false);
  const scanning = params.mode === "scan";
  const target = {
    packetId: params.packetId ? Number(params.packetId) : undefined,
    trayId: params.trayId ? Number(params.trayId) : undefined,
    plantingId: params.plantingId ? Number(params.plantingId) : undefined,
    taskId: params.taskId ? Number(params.taskId) : undefined,
  };

  async function shoot() {
    if (!camera.current || allotmentId === null) return;
    setBusy(true);
    try {
      const photo = await camera.current.takePictureAsync({ quality: 0.9 });
      const clientId = newId();
      const uri = await keepPhoto(photo.uri, clientId);
      await queue.enqueue(
        "upload",
        {
          allotmentId,
          uri,
          name: `${clientId}.jpg`,
          mimeType: "image/jpeg",
          fields: scanning ? scanFields(clientId) : photoFields(target, clientId),
          deleteAfterUpload: true,
        },
        clientId,
      );
      setTaken((n) => n + 1);
      void queue.run();
    } finally {
      setBusy(false);
    }
  }

  if (!permission) return <Screen title={scanning ? "Scan a packet" : "Take a photo"}><T muted>Checking the camera…</T></Screen>;
  if (!permission.granted) {
    return (
      <Screen title={scanning ? "Scan a packet" : "Take a photo"} subtitle="Allotment needs the camera for this.">
        <Button label="Allow the camera" onPress={() => void ask()} />
      </Screen>
    );
  }
  return (
    <Screen
      title={scanning ? "Scan a packet" : "Take a photo"}
      subtitle={scanning ? "The back of the packet, flat, in good light, filling the frame. It is read for you to check." : undefined}
      scroll={false}
      footer={
        <View style={{ gap: space.sm }}>
          {taken > 0 ? (
            <Banner tone="ok" text={scanning ? `${taken} sent to be read. They appear under "To review" in Seeds.` : `${taken} photo${taken === 1 ? "" : "s"} saved; sending when there is signal.`} />
          ) : null}
          <Button label={busy ? "Saving…" : "Take photo"} onPress={() => void shoot()} busy={busy} />
          <Button label={taken > 0 ? "Done" : "Cancel"} kind="secondary" onPress={() => router.back()} />
        </View>
      }
    >
      <View style={{ flex: 1, minHeight: 320, borderRadius: 12, overflow: "hidden" }}>
        <CameraView ref={camera} style={{ flex: 1 }} facing="back" />
      </View>
    </Screen>
  );
}
