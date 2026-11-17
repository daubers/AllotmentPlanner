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
