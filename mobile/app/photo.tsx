import { CameraView, useCameraPermissions } from "expo-camera";
import { ImageManipulator, SaveFormat } from "expo-image-manipulator";
import * as ImagePicker from "expo-image-picker";
import { useLocalSearchParams, useRouter } from "expo-router";
import React, { useRef, useState } from "react";
import { Image, Pressable, ScrollView, View } from "react-native";
import { forget, removeWhenSent, sentMediaId } from "../src/capture/sent";
import { keepPhoto } from "../src/capture/storage";
import { removeFile } from "../src/queue/nativeUpload";
import { showDialog } from "../src/ui/dialog";
import UploadBanner from "../src/ui/UploadBanner";
import { newId } from "../src/queue/queue";
import { photoFields, scanFields } from "../src/seeds/model";
import { useApp } from "../src/state/AppProvider";
import { Banner, Button, Screen, T } from "../src/ui/kit";
import { space } from "../src/ui/theme";

function Thumbnails({ photos, onRemove }: { photos: { id: string; uri: string }[]; onRemove: (id: string) => void }) {
  if (photos.length === 0) return null;
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: space.sm }} accessibilityLabel="Photos saved so far">
      {photos.map((ph, i) => (
        <Pressable key={ph.id} onPress={() => onRemove(ph.id)} accessibilityRole="button" accessibilityLabel={`Photo ${i + 1}. Tap to remove`}>
          <Image source={{ uri: ph.uri }} style={{ width: 64, height: 64, borderRadius: 8 }} />
        </Pressable>
      ))}
    </ScrollView>
  );
}

/** One camera screen for every kind of photo that is not a map walk: the back of a packet (read into
 *  a draft), or a photo of a packet, tray or planting. The photo is queued and sent when there is signal. */
export default function Photo() {
  const { queue, allotmentId } = useApp();
  const router = useRouter();
  const params = useLocalSearchParams<{ mode?: string; packetId?: string; trayId?: string; plantingId?: string; taskId?: string }>();
  const [permission, ask] = useCameraPermissions();
  const camera = useRef<CameraView>(null);
  const [taken, setTaken] = useState(0);
  const [thumbs, setThumbs] = useState<{ id: string; uri: string }[]>([]);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const scanning = params.mode === "scan";
  const target = {
    packetId: params.packetId ? Number(params.packetId) : undefined,
    trayId: params.trayId ? Number(params.trayId) : undefined,
    plantingId: params.plantingId ? Number(params.plantingId) : undefined,
    taskId: params.taskId ? Number(params.taskId) : undefined,
  };

  /** Keep a photo in the app's own storage and queue it for upload. */
  async function queuePhoto(tempUri: string, mimeType = "image/jpeg") {
    if (allotmentId === null) return;
    const ext = mimeType === "image/png" ? "png" : mimeType === "image/webp" ? "webp" : mimeType === "image/heic" ? "heic" : "jpg";
    const clientId = newId();
    // A small preview for the strip under the camera, made before the original is moved away. Never blocks saving.
    try {
      const small = await ImageManipulator.manipulate(tempUri).resize({ width: 192 }).renderAsync();
      const saved = await small.saveAsync({ compress: 0.6, format: SaveFormat.JPEG });
      setThumbs((t) => [...t, { id: clientId, uri: saved.uri }]);
    } catch {
      /* no preview; the photo is still saved */
    }
    const uri = await keepPhoto(tempUri, clientId, ext);
    await queue.enqueue(
      "upload",
      {
        allotmentId,
        uri,
        name: `${clientId}.${ext}`,
        mimeType,
        fields: scanning ? scanFields(clientId) : photoFields(target, clientId),
        deleteAfterUpload: true,
      },
      clientId,
    );
    setTaken((n) => n + 1);
  }

  async function shoot() {
    if (!camera.current || allotmentId === null) return;
    setBusy(true);
    try {
      const photo = await camera.current.takePictureAsync({ quality: 0.9 });
      await queuePhoto(photo.uri);
      void queue.run();
    } finally {
      setBusy(false);
    }
  }

  /** Choose any number of photos from the library. They are copied, so the originals stay where they are. */
  async function pick() {
    if (allotmentId === null) return;
    setBusy(true);
    try {
      const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ["images"], allowsMultipleSelection: true, quality: 0.9 });
      if (result.canceled) return;
      for (const asset of result.assets) await queuePhoto(asset.uri, asset.mimeType ?? "image/jpeg");
      void queue.run();
    } finally {
      setBusy(false);
    }
  }

  /** Take a photo back: before it is sent just drop it; while it is going up remove it the moment it lands; after, delete it on the server. */
  async function remove(clientId: string) {
    setNote(null);
    if (queue.state().active?.id === clientId) {
      removeWhenSent(clientId);
    } else {
      const job = (await queue.jobs()).find((j) => j.id === clientId);
      if (job) {
        await queue.drop(clientId);
        try {
          removeFile((job.payload as { uri: string }).uri);
        } catch {
          /* already gone */
        }
      } else {
        const mediaId = sentMediaId(clientId);
        if (mediaId === undefined || allotmentId === null) {
          setNote("Couldn't take that one back from here. You can delete it from the job on the web.");
          return;
        }
        await queue.enqueue("request", { method: "DELETE", path: `/api/v1/allotments/${allotmentId}/media/${mediaId}` });
        forget(clientId);
        void queue.run();
      }
    }
    setThumbs((t) => t.filter((x) => x.id !== clientId));
    setTaken((n) => Math.max(0, n - 1));
  }

  function askRemove(clientId: string) {
    showDialog({
      title: "Remove this photo?",
      message: "It will be taken off the job.",
      actions: [
        { label: "Remove", kind: "primary", onPress: () => void remove(clientId) },
        { label: "Keep", kind: "secondary" },
      ],
    });
  }

  if (!permission) return <Screen title={scanning ? "Scan a packet" : "Take a photo"}><T muted>Checking the camera…</T></Screen>;
  if (!permission.granted) {
    return (
      <Screen title={scanning ? "Scan a packet" : "Take a photo"} subtitle="Allotment needs the camera for this.">
        <View style={{ gap: space.sm }}>
          <Button label="Allow the camera" onPress={() => void ask()} />
          <Button label="Choose from library instead" kind="secondary" onPress={() => void pick()} disabled={busy} />
          <UploadBanner />
          {taken > 0 ? <Banner tone="ok" text={`${taken} photo${taken === 1 ? "" : "s"} saved on this phone.`} /> : null}
          <Thumbnails photos={thumbs} onRemove={askRemove} />
        </View>
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
            <Banner tone="ok" text={scanning ? `${taken} sent to be read. They appear under "To review" in Seeds.` : `${taken} photo${taken === 1 ? "" : "s"} saved on this phone.`} />
          ) : null}
          <UploadBanner />
          <Thumbnails photos={thumbs} onRemove={askRemove} />
          {note ? <Banner tone="warn" text={note} /> : null}
          <Button label={busy ? "Saving…" : "Take photo"} onPress={() => void shoot()} busy={busy} />
          <Button label="Choose from library" kind="secondary" onPress={() => void pick()} disabled={busy} />
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
