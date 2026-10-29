import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, getSession, setSession, setSessionExpiredHandler } from "./api/client";

type User = { id?: number; email?: string; display_name?: string };

type AuthState = {
  user: User | null;
  loading: boolean;
  login(email: string, password: string): Promise<string | null>;
  register(email: string, displayName: string, password: string, inviteCode?: string): Promise<string | null>;
  logout(): void;
};

const AuthContext = createContext<AuthState | null>(null);

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

function errorMessage(error: unknown, fallback: string): string {
  const e = error as { message?: string; errors?: { json?: Record<string, string[]> } } | undefined;
  const first = e?.errors?.json && Object.values(e.errors.json).flat()[0];
  return first ?? e?.message ?? fallback;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(!!getSession());

  const logout = useCallback(() => {
    setSession(null);
    setUser(null);
  }, []);

  useEffect(() => {
    setSessionExpiredHandler(() => setUser(null));
    if (!getSession()) return;
    api.GET("/api/v1/auth/me").then(({ data }) => {
      setUser(data ?? null);
      setLoading(false);
    });
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      user,
      loading,
      logout,
      async login(email, password) {
        const { data, error } = await api.POST("/api/v1/auth/login", { body: { email, password } });
        if (!data) return errorMessage(error, "Login failed");
        setSession({ access_token: data.access_token!, refresh_token: data.refresh_token! });
        setUser(data.user ?? null);
        return null;
      },
      async register(email, display_name, password, inviteCode) {
        const { data, error } = await api.POST("/api/v1/auth/register", {
          body: { email, display_name, password, ...(inviteCode ? { invite_code: inviteCode } : {}) },
        });
        if (!data) return errorMessage(error, "Registration failed");
        setSession({ access_token: data.access_token!, refresh_token: data.refresh_token! });
        setUser(data.user ?? null);
        return null;
      },
    }),
    [user, loading, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
