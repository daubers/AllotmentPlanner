/** Server address and login tokens, kept in a small key-value store (the phone's secure storage). */

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

/** "192.168.1.5:8000" or "https://plot.example.com/" become a base URL without a trailing slash. */
export function normaliseServerUrl(input: string): string {
  let url = input.trim();
  if (!url) return "";
  if (!/^https?:\/\//i.test(url)) url = `http://${url}`;
  return url.replace(/\/+$/, "");
}

export class LoginError extends Error {}

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
    const body = (await res.json()) as Tokens;
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
