import { SSO_REDIRECT } from "../auth/session";

/** What the account screen needs from the signed-in session. */
export interface AccountSession {
  serverUrl: string;
  authHeader(): Promise<string | undefined>;
}

export type ExportState = { id: number; status: "pending" | "ready" | "failed" | "expired"; url?: string | null };
export type Methods = { has_password: boolean; identities: { id: number; provider: string; provider_name?: string | null }[] };

/** Why deleting was refused: the person is the only owner of allotments shared with others. */
export class SharedAllotmentsError extends Error {
  constructor(message: string, readonly allotments: { id: number; name: string }[]) {
    super(message);
  }
}

async function call(session: AccountSession, method: string, path: string, body?: unknown, fetchImpl: typeof fetch = (...a) => fetch(...a)) {
  const auth = await session.authHeader();
  return fetchImpl(`${session.serverUrl}${path}`, {
    method,
    headers: { ...(auth ? { Authorization: auth } : {}), ...(body ? { "Content-Type": "application/json" } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
}

async function failure(res: Response, fallback: string): Promise<string> {
  try {
    return ((await res.json()) as { message?: string }).message ?? fallback;
  } catch {
    return fallback;
  }
}

export async function loadMethods(session: AccountSession, fetchImpl?: typeof fetch): Promise<Methods> {
  const res = await call(session, "GET", "/api/v1/auth/oidc/identities", undefined, fetchImpl);
  if (!res.ok) throw new Error(await failure(res, "Could not load your sign-in methods"));
  return (await res.json()) as Methods;
}

export async function requestExport(session: AccountSession, fetchImpl?: typeof fetch): Promise<ExportState> {
  const res = await call(session, "POST", "/api/v1/auth/me/export", undefined, fetchImpl);
  if (!res.ok) throw new Error(await failure(res, "Could not start the export"));
  return (await res.json()) as ExportState;
}

export async function exportStatus(session: AccountSession, id: number, fetchImpl?: typeof fetch): Promise<ExportState> {
  const res = await call(session, "GET", `/api/v1/auth/me/export/${id}`, undefined, fetchImpl);
  if (!res.ok) throw new Error(await failure(res, "Could not check the export"));
  return (await res.json()) as ExportState;
}

/** The full address to open for an export's download link, which the server gives relative. */
export const downloadUrl = (session: AccountSession, url: string): string => `${session.serverUrl}${url}`;

/** The address that has the person confirm at their provider; the server sends the phone back after. */
export async function startReauth(session: AccountSession, providerId: string, fetchImpl?: typeof fetch): Promise<string> {
  const path = `/api/v1/auth/oidc/${encodeURIComponent(providerId)}/reauth?client=mobile&redirect=${encodeURIComponent(SSO_REDIRECT)}`;
  const res = await call(session, "POST", path, undefined, fetchImpl);
  if (!res.ok) throw new Error(await failure(res, "Could not start confirming"));
  return `${session.serverUrl}${((await res.json()) as { url: string }).url}`;
}

/** The confirmation code or error a provider confirmation ended with (`allotment://auth?reauth=...`). */
export function parseReauthResult(url: string): { code?: string; error?: string } {
  const params = new URLSearchParams(url.split("#")[0].split("?")[1] ?? "");
  const code = params.get("reauth");
  return code ? { code } : { error: params.get("error") ?? "failed" };
}

export const REAUTH_ERRORS: Record<string, string> = {
  wrong_account: "That is not the account you are signed in to. Sign in with the same provider login.",
  denied: "Confirming was cancelled or refused at the provider.",
  reauth_expired: "That took too long. Please try again.",
  expired: "That took too long. Please try again.",
  invalid_state: "That could not be completed. Please try again.",
};
export const reauthMessage = (code: string): string => REAUTH_ERRORS[code] ?? "Confirming failed. Please try again.";

export async function deleteAccount(
  session: AccountSession,
  proof: { password?: string; reauth_code?: string },
  fetchImpl?: typeof fetch,
): Promise<void> {
  const res = await call(session, "DELETE", "/api/v1/auth/me", proof, fetchImpl);
  if (res.ok) return;
  let body: { message?: string; errors?: { allotments?: { id: number; name: string }[] } } = {};
  try {
    body = await res.json();
  } catch {
    /* no body */
  }
  if (res.status === 409 && body.errors?.allotments) {
    throw new SharedAllotmentsError(body.message ?? "Hand over your shared allotments first", body.errors.allotments);
  }
  throw new Error(body.message ?? "Could not delete the account");
}
