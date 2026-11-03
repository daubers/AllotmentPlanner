import type { Session } from "../auth/session";
import { PermanentError, RetryableError, type Handler } from "./queue";

export type UploadArgs = {
  url: string;
  uri: string;
  name: string;
  mimeType: string;
  fields: Record<string, string>;
  headers: Record<string, string>;
  onProgress: (fraction: number) => void;
};
export type UploadResult = { status: number; body: string };

export type Deps = {
  session: Session;
  fetchImpl?: typeof fetch;
  uploadFile: (args: UploadArgs) => Promise<UploadResult>;
  /** Delete a local file once it is safely on the server. */
  removeFile?: (uri: string) => void;
  /** Told when an upload is on the server: the id the app gave it (its client_id), the server's id for it, and the allotment. */
  onUploaded?: (clientId: string, mediaId: number, allotmentId: number) => void;
};

export type RequestJob = { method: "POST" | "PUT" | "PATCH" | "DELETE"; path: string; body?: unknown };
export type UploadJob = {
  allotmentId: number;
  uri: string;
  name: string;
  mimeType: string;
  /** Extra form fields the API accepts, such as feature_id or task_id. */
  fields?: Record<string, string>;
  /** The file is a copy the app made for this upload: delete it once the server has it. */
  deleteAfterUpload?: boolean;
};

function reasonFrom(body: string): string | null {
  try {
    const json = JSON.parse(body);
    return json.message ?? json.detail ?? null;
  } catch {
    return null;
  }
}

/** Turn a response into success, a retry later, or a permanent failure with the server's reason. */
export async function checkResponse(status: number, body: string, session: Session): Promise<void> {
  if (status >= 200 && status < 300) return;
  if (status === 401) {
    await session.rejected();
    throw new RetryableError("Signed out: sign in again to send this");
  }
  if (status === 408 || status === 429 || status >= 500) {
    throw new RetryableError(`The server is busy (HTTP ${status})`);
  }
  if (status === 413) throw new PermanentError("Too large for the server");
  throw new PermanentError(reasonFrom(body) ?? `The server refused it (HTTP ${status})`);
}

export function makeHandlers(deps: Deps): Record<string, Handler> {
  const doFetch = deps.fetchImpl ?? ((...args: Parameters<typeof fetch>) => fetch(...args));
  return {
    async request(payload: RequestJob) {
      const header = await deps.session.authHeader();
      let res: Response;
      try {
        res = await doFetch(`${deps.session.serverUrl}${payload.path}`, {
          method: payload.method,
          headers: {
            Accept: "application/json",
            ...(payload.body !== undefined ? { "Content-Type": "application/json" } : {}),
            ...(header ? { Authorization: header } : {}),
          },
          body: payload.body !== undefined ? JSON.stringify(payload.body) : undefined,
        });
      } catch {
        throw new RetryableError("No connection");
      }
      await checkResponse(res.status, await res.text(), deps.session);
    },

    async upload(payload: UploadJob, ctx) {
      const header = await deps.session.authHeader();
      let result: UploadResult;
      try {
        result = await deps.uploadFile({
          url: `${deps.session.serverUrl}/api/v1/allotments/${payload.allotmentId}/media`,
          uri: payload.uri,
          name: payload.name,
          mimeType: payload.mimeType,
          fields: payload.fields ?? {},
          headers: { Accept: "application/json", ...(header ? { Authorization: header } : {}) },
          onProgress: ctx.onProgress,
        });
      } catch {
        throw new RetryableError("The connection dropped while uploading");
      }
      await checkResponse(result.status, result.body, deps.session);
      ctx.onProgress(1);
      const clientId = payload.fields?.client_id;
      if (clientId) {
        try {
          const id = JSON.parse(result.body)?.id;
          if (typeof id === "number") deps.onUploaded?.(clientId, id, payload.allotmentId);
        } catch {
          /* no id in the answer: it just can't be taken back from the app */
        }
      }
      if (payload.deleteAfterUpload) {
        try {
          deps.removeFile?.(payload.uri);
        } catch {
          /* already gone: nothing to clean up */
        }
      }
    },
  };
}
