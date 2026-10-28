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
};

export type RequestJob = { method: "POST" | "PUT" | "PATCH" | "DELETE"; path: string; body?: unknown };
export type UploadJob = {
  allotmentId: number;
  uri: string;
  name: string;
  mimeType: string;
  /** Extra form fields the API accepts, such as feature_id or task_id. */
  fields?: Record<string, string>;
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
    },
  };
}
