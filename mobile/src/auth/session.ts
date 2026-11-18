/** Server address and login tokens, kept in a small key-value store (the phone's secure storage). */

import type { ServerInfo } from "./compat";

export type Tokens = { access_token: string; refresh_token: string };

export interface KeyValueStore {
  get(key: string): Promise<string | null>;
  set(key: string, value: string): Promise<void>;
  remove(key: string): Promise<void>;
}

const SERVER = "allotment.server";
const TOKENS = "allotment.tokens";

/** Seconds until a JWT expires, or 0 if it can't be decoded. */
export function secondsLeft(jwt: string, now: number = Date.now()): number {
  try {
    const payload = JSON.parse(atob(jwt.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return payload.exp - now / 1000;
  } catch {
    return 0;
  }
}

/** Whether an address is on this phone's own network: a private IPv4 range, localhost, a `.local` name, or a bare host name. */
export function isLocalHost(hostPort: string): boolean {
  const host = hostPort.replace(/^\[|\]?(:\d+)?$/g, "").toLowerCase();
  if (host === "localhost" || host.endsWith(".local") || !host.includes(".")) return true;
  const m = host.match(/^(\d{1,3})\.(\d{1,3})\.\d{1,3}\.\d{1,3}$/);
  if (!m) return false;
  const [a, b] = [Number(m[1]), Number(m[2])];
  return a === 10 || a === 127 || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168) || (a === 169 && b === 254);
}

/**
 * "192.168.1.5:8000" or "https://plot.example.com/" become a base URL without a trailing slash.
 * With no scheme, an address on the local network gets http:// (a home server rarely has a certificate)
 * and anything else gets https://.
 */
export function normaliseServerUrl(input: string): string {
  let url = input.trim();
  if (!url) return "";
  if (!/^https?:\/\//i.test(url)) url = `${isLocalHost(url.split("/")[0]) ? "http" : "https"}://${url}`;
  return url.replace(/\/+$/, "");
}

export class LoginError extends Error {}

/** A single sign-on provider the server offers. */
export type Provider = { id: string; name: string };

/** What to tell someone when single sign-on sends them back with an error code. */
const SSO_ERRORS: Record<string, string> = {
  not_invited: "There is no account for that address. Ask for an invite, then sign in with the same email.",
  email_unverified: "The provider has not verified that email address, so it can't be used to sign in.",
  no_email: "The provider did not share an email address.",
  denied: "Sign-in was cancelled or refused at the provider.",
  expired: "That sign-in took too long. Please try again.",
  invalid_state: "That sign-in could not be completed. Please try again.",
  provider_unreachable: "The sign-in provider could not be reached. Try again in a moment.",
};
export const ssoMessage = (code: string): string => SSO_ERRORS[code] ?? "Sign-in failed. Please try again.";

/** The address the server sends the phone back to, and where the sign-in page's result is read from. */
export const SSO_REDIRECT = "allotment://auth";

/** The one-time code or error code a sign-in ended with (`allotment://auth?code=...`). */
export function parseSignInResult(url: string): { code?: string; error?: string } {
  const query = url.split("#")[0].split("?")[1] ?? "";
  const params = new URLSearchParams(query);
  const code = params.get("code");
  const error = params.get("error");
  return code ? { code } : { error: error ?? "failed" };
}

/** The address that starts a sign-in at a provider; the server redirects on to the provider. */
export const signInUrl = (base: string, providerId: string): string =>
  `${base}/api/v1/auth/oidc/${encodeURIComponent(providerId)}/login?client=mobile&redirect=${encodeURIComponent(SSO_REDIRECT)}`;

export class Session {
  serverUrl = "";
  private tokens: Tokens | null = null;
  private refreshing: Promise<void> | null = null;
  private expiredListeners = new Set<() => void>();
  private changeListeners = new Set<() => void>();

  constructor(
    private readonly store: KeyValueStore,
    private readonly fetchImpl: typeof fetch = (...args) => fetch(...args),
  ) {}

  async load(): Promise<void> {
    this.serverUrl = (await this.store.get(SERVER)) ?? "";
    try {
      const raw = await this.store.get(TOKENS);
      this.tokens = raw ? (JSON.parse(raw) as Tokens) : null;
    } catch {
      this.tokens = null;
    }
    this.changed();
  }

  get signedIn(): boolean {
    return this.tokens !== null;
  }

  onChange(fn: () => void): () => void {
    this.changeListeners.add(fn);
    return () => this.changeListeners.delete(fn);
  }

  /** Called when the server refuses the saved login, so the app can return to the sign-in screen. */
  onExpired(fn: () => void): () => void {
    this.expiredListeners.add(fn);
    return () => this.expiredListeners.delete(fn);
  }

  async login(serverInput: string, email: string, password: string): Promise<void> {
    const base = normaliseServerUrl(serverInput);
    if (!base) throw new LoginError("Enter the server address");
    let res: Response;
    try {
      res = await this.fetchImpl(`${base}/api/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ email, password }),
      });
    } catch {
      throw new LoginError(`Can't reach ${base}. Check the address and that you are online.`);
    }
    if (res.status === 401) throw new LoginError("Wrong email or password");
    if (!res.ok) throw new LoginError(`The server answered ${res.status}`);
    await this.adopt(base, (await res.json()) as Tokens);
  }

  /** What the server says about itself before anyone signs in, or null if it can't be read. */
  async serverInfo(serverInput: string): Promise<(ServerInfo & { providers: Provider[] }) | null> {
    const base = normaliseServerUrl(serverInput);
    if (!base) return null;
    try {
      const res = await this.fetchImpl(`${base}/api/v1/auth/config`, { headers: { Accept: "application/json" } });
      if (!res.ok) return null;
      const body = (await res.json()) as { oidc?: Provider[]; server_version?: string; api_level?: number; min_app_version?: string };
      return {
        providers: (body.oidc ?? []).filter((p) => p.id && p.name),
        serverVersion: body.server_version,
        apiLevel: body.api_level,
        minAppVersion: body.min_app_version,
      };
    } catch {
      return null;
    }
  }

  /** The single sign-on providers this server offers (none if it can't be reached or has none). */
  async providers(serverInput: string): Promise<Provider[]> {
    return (await this.serverInfo(serverInput))?.providers ?? [];
  }

  /** Finish a single sign-on: swap the one-time code the sign-in ended with for a login. */
  async loginWithCode(serverInput: string, code: string): Promise<void> {
    const base = normaliseServerUrl(serverInput);
    if (!base) throw new LoginError("Enter the server address");
    let res: Response;
    try {
      res = await this.fetchImpl(`${base}/api/v1/auth/oidc/exchange`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ code }),
      });
    } catch {
      throw new LoginError(`Can't reach ${base}. Check the address and that you are online.`);
    }
    if (res.status === 401) throw new LoginError("That sign-in has expired. Please try again.");
    if (!res.ok) throw new LoginError(`The server answered ${res.status}`);
    await this.adopt(base, (await res.json()) as Tokens);
  }

  private async adopt(base: string, body: Tokens): Promise<void> {
    this.serverUrl = base;
    this.tokens = { access_token: body.access_token, refresh_token: body.refresh_token };
    await this.store.set(SERVER, base);
    await this.store.set(TOKENS, JSON.stringify(this.tokens));
    this.changed();
  }

  async logout(): Promise<void> {
    this.tokens = null;
    await this.store.remove(TOKENS);
    this.changed();
  }

  /** The Authorization header value, refreshing a token that is about to expire. */
  async authHeader(): Promise<string | undefined> {
    if (this.tokens && secondsLeft(this.tokens.access_token) < 60) {
      this.refreshing ??= this.refresh().finally(() => (this.refreshing = null));
      await this.refreshing;
    }
    return this.tokens ? `Bearer ${this.tokens.access_token}` : undefined;
  }

  /** Call when the server says the login is no longer valid. */
  async rejected(): Promise<void> {
    if (!this.tokens) return;
    await this.logout();
    this.expiredListeners.forEach((fn) => fn());
  }

  private async refresh(): Promise<void> {
    if (!this.tokens) return;
    try {
      const res = await this.fetchImpl(`${this.serverUrl}/api/v1/auth/refresh`, {
        method: "POST",
        headers: { Authorization: `Bearer ${this.tokens.refresh_token}`, Accept: "application/json" },
      });
      if (res.ok) {
        const body = (await res.json()) as { access_token?: string };
        if (body.access_token) {
          this.tokens = { ...this.tokens, access_token: body.access_token };
          await this.store.set(TOKENS, JSON.stringify(this.tokens));
          return;
        }
      }
      // No signal is not the same as a refused login: only a real rejection signs the person out.
      if (res.status === 401 || res.status === 422) await this.rejected();
    } catch {
      /* offline: keep the old token; the request that follows will fail and be retried */
    }
  }

  private changed(): void {
    this.changeListeners.forEach((fn) => fn());
  }
}
