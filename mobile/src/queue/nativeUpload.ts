import { File, UploadType } from "expo-file-system";
import type { UploadArgs, UploadResult } from "./handlers";

/** Stream a file from disk as a multipart form (the file is never loaded into memory, so a
 *  multi-gigabyte video is fine). On iOS the transfer can carry on while the app is in the background. */
export async function uploadFile(args: UploadArgs): Promise<UploadResult> {
  if (process.env.EXPO_PUBLIC_DEMO === "1") {
    // The demo has a fake server for ordinary requests but this goes straight to the network, where the
    // fake login is refused and signs you out. Pretend it was sent.
    args.onProgress(1);
    return { status: 201, body: JSON.stringify({ id: Math.floor(Math.random() * 1e6) }) };
  }
  const file = new File(args.uri);
  const res = await file.upload(args.url, {
    httpMethod: "POST",
    uploadType: UploadType.MULTIPART,
    fieldName: "file",
    mimeType: args.mimeType,
    parameters: args.fields,
    headers: args.headers,
    onProgress: ({ bytesSent, totalBytes }) => {
      if (totalBytes > 0) args.onProgress(Math.min(1, bytesSent / totalBytes));
    },
  });
  return { status: res.status, body: res.body };
}

export function removeFile(uri: string): void {
  const file = new File(uri);
  if (file.exists) file.delete();
}
