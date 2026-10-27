import createClient, { type Middleware } from "openapi-fetch";
import type { components, paths } from "./schema";

export type Tokens = { access_token: string; refresh_token: string };
export type Allotment = components["schemas"]["Allotment"];

const KEY = "allotment.tokens";

export function loadTokens(): Tokens | null {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Tokens) : null;
  } catch {
    return null;
  }
}

export function saveTokens(tokens: Tokens | null): void {
  try {
    if (tokens) localStorage.setItem(KEY, JSON.stringify(tokens));
    else localStorage.removeItem(KEY);
  } catch {
    /* storage unavailable: session lasts until reload */
  }
}

/** Seconds until a JWT expires, or 0 if it can't be decoded. */
export function secondsLeft(jwt: string): number {
  try {
    const payload = JSON.parse(atob(jwt.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return payload.exp - Date.now() / 1000;
  } catch {
    return 0;
  }
}

let tokens: Tokens | null = loadTokens();
let refreshing: Promise<void> | null = null;
let onSessionExpired: () => void = () => {};

export function setSession(next: Tokens | null): void {
  tokens = next;
  saveTokens(next);
}
export function getSession(): Tokens | null {
  return tokens;
}
export function setSessionExpiredHandler(fn: () => void): void {
  onSessionExpired = fn;
}

const raw = createClient<paths>({ baseUrl: "" });

async function refresh(): Promise<void> {
  if (!tokens) return;
  const { data } = await raw.POST("/api/v1/auth/refresh", {
    headers: { Authorization: `Bearer ${tokens.refresh_token}` },
  });
  if (data?.access_token) setSession({ ...tokens, access_token: data.access_token });
  else {
    setSession(null);
    onSessionExpired();
  }
}

const auth: Middleware = {
  async onRequest({ request }) {
    if (request.url.includes("/api/v1/auth/") && !request.url.endsWith("/auth/me")) return request;
    if (tokens && secondsLeft(tokens.access_token) < 60) {
      refreshing ??= refresh().finally(() => (refreshing = null));
      await refreshing;
    }
    if (tokens) request.headers.set("Authorization", `Bearer ${tokens.access_token}`);
    return request;
  },
  async onResponse({ response }) {
    if (response.status === 401 && tokens) {
      setSession(null);
      onSessionExpired();
    }
    return response;
  },
};

export const api = createClient<paths>({ baseUrl: "" });
api.use(auth);
