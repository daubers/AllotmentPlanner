import { authHeader, sessionRejected } from "../api/client";
import { formatSize, type Media } from "./group";

/** Why a file can't be uploaded, decided before anything is sent; null if it is fine. */
export function checkFileSize(file: Pick<File, "name" | "size">, maxBytes: number | undefined): string | null {
  if (maxBytes && file.size > maxBytes) {
    return `${file.name} is ${formatSize(file.size)}, but the largest upload allowed is ${formatSize(maxBytes)}`;
  }
  return null;
}

/** What to tell the person when the connection fails mid-upload: the browser's own message
 *  ("NetworkError when attempting to fetch resource") says nothing useful. */
export function networkFailureMessage(file: Pick<File, "name" | "size">, maxBytes: number | undefined): string {
  const tooBig = checkFileSize(file, maxBytes);
  if (tooBig) return `${tooBig}. Try a shorter clip or a lower resolution.`;
  return `The connection dropped while uploading ${formatSize(file.size)}. Check your connection and try again.`;
}

export type UploadOptions = {
  file: Pick<File, "name" | "size">;
  onProgress?: (fraction: number) => void;
  maxBytes?: number;
  /** Injected in tests. */
  newRequest?: () => XMLHttpRequest;
};

/** POST a multipart form with upload progress. Resolves with the created media item. */
export async function sendUpload(url: string, form: FormData, opts: UploadOptions): Promise<Media> {
  const { file, onProgress, maxBytes } = opts;
  const tooBig = checkFileSize(file, maxBytes);
  if (tooBig) throw new Error(tooBig);
  const header = await authHeader();
  return new Promise<Media>((resolve, reject) => {
    const xhr = (opts.newRequest ?? (() => new XMLHttpRequest()))();
    xhr.open("POST", url);
    if (header) xhr.setRequestHeader("Authorization", header);
    xhr.setRequestHeader("Accept", "application/json");
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && e.total > 0) onProgress?.(Math.min(1, e.loaded / e.total));
    };
    xhr.onerror = () => reject(new Error(networkFailureMessage(file, maxBytes)));
    xhr.onabort = () => reject(new Error("Upload cancelled"));
    xhr.onload = () => {
      let body: { message?: string } | null = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        /* not JSON (e.g. a proxy's HTML error page) */
      }
      if (xhr.status === 401) sessionRejected();
      if (xhr.status >= 200 && xhr.status < 300 && body) {
        onProgress?.(1);
        resolve(body as unknown as Media);
      } else if (xhr.status === 413) {
        reject(new Error(`${file.name} is too large for the server${maxBytes ? ` (limit ${formatSize(maxBytes)})` : ""}`));
      } else {
        reject(new Error(body?.message ?? `Upload failed (HTTP ${xhr.status})`));
      }
    };
    xhr.send(form);
  });
}
