import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components } from "../api/schema";

export type AuthMethods = components["schemas"]["AuthMethods"];
export type LinkedIdentity = components["schemas"]["OidcIdentity"];

const failure = (error: unknown, fallback: string) => (error as { message?: string } | undefined)?.message ?? fallback;

/** How the signed-in user can sign in: a password, and any providers they have linked. */
export function useAuthMethods() {
  return useQuery({
    queryKey: ["auth-methods"],
    queryFn: async (): Promise<AuthMethods> =>
      (await api.GET("/api/v1/auth/oidc/identities")).data ?? { has_password: true, identities: [] },
  });
}

/** The providers the server offers (the same list the login page shows). */
export function useProviders() {
  return useQuery({
    queryKey: ["auth-config"],
    queryFn: async () => (await api.GET("/api/v1/auth/config")).data?.oidc ?? [],
  });
}

export function useUnlink() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      const { error } = await api.DELETE("/api/v1/auth/oidc/identities/{identity_id}", {
        params: { path: { identity_id: id } },
      });
      if (error) throw new Error(failure(error, "Could not unlink"));
    },
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["auth-methods"] }),
  });
}

/** Ask the server to begin linking; resolves to the address to send the browser to. */
export async function startLink(providerId: string): Promise<string> {
  const { data, error } = await api.POST("/api/v1/auth/oidc/{provider_id}/link", {
    params: { path: { provider_id: providerId } },
  });
  if (!data?.url) throw new Error(failure(error, "Could not start linking"));
  return data.url;
}

export type AccountExport = components["schemas"]["AccountExport"];

/** Ask for a zip of the person's data; it is built in the background. */
export function useRequestExport() {
  return useMutation({
    mutationFn: async (): Promise<AccountExport> => {
      const { data, error } = await api.POST("/api/v1/auth/me/export");
      if (!data) throw new Error(failure(error, "Could not start the export"));
      return data;
    },
  });
}

/** Where an export has got to. Polls until it is ready, failed or expired. */
export function useExportStatus(id: number | null) {
  return useQuery({
    queryKey: ["account-export", id],
    enabled: id !== null,
    queryFn: async (): Promise<AccountExport> => {
      const { data, error } = await api.GET("/api/v1/auth/me/export/{export_id}", {
        params: { path: { export_id: id! } },
      });
      if (!data) throw new Error(failure(error, "Could not check the export"));
      return data;
    },
    refetchInterval: (query) => (query.state.data?.status === "pending" ? 2000 : false),
  });
}

/** Begin proving it is you at a provider; resolves to the address to send the browser to. */
export async function startReauth(providerId: string): Promise<string> {
  const { data, error } = await api.POST("/api/v1/auth/oidc/{provider_id}/reauth", {
    params: { path: { provider_id: providerId } },
  });
  if (!data?.url) throw new Error(failure(error, "Could not start confirming"));
  return data.url;
}

/** Allotments blocking deletion: the person is their only owner and others belong to them. */
export class SharedAllotmentsError extends Error {
  constructor(message: string, readonly allotments: { id: number; name: string }[]) {
    super(message);
  }
}

/** Delete the account, confirmed by the password or by a code from `startReauth`. */
export async function deleteAccount(proof: { password?: string; reauth_code?: string }): Promise<void> {
  const { error, response } = await api.DELETE("/api/v1/auth/me", { body: proof });
  if (!error) return;
  const body = error as { message?: string; errors?: { allotments?: { id: number; name: string }[] } } | undefined;
  if (response?.status === 409 && body?.errors?.allotments) {
    throw new SharedAllotmentsError(body.message ?? "Hand over your shared allotments first", body.errors.allotments);
  }
  throw new Error(failure(error, "Could not delete the account"));
}
