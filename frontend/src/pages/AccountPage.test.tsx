import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
const post = vi.fn();
const del = vi.fn();
vi.mock("../api/client", () => ({
  api: { GET: (...a: unknown[]) => get(...a), POST: (...a: unknown[]) => post(...a), DELETE: (...a: unknown[]) => del(...a) },
  getSession: () => null,
  setSession: vi.fn(),
  setSessionExpiredHandler: vi.fn(),
}));

import { AuthProvider } from "../auth";
import AccountPage from "./AccountPage";

const CONFIG = { registration: "invite", oidc: [{ id: "authentik", name: "Authentik" }, { id: "google", name: "Google" }] };
const linkedAuthentik = { id: 7, provider: "authentik", provider_name: "Authentik", email: "me@elsewhere.test", created_at: "2026-11-17T10:00:00Z" };

function serve(methods: object, config: object = CONFIG) {
  get.mockImplementation(async (path: string) => {
    if (path === "/api/v1/auth/oidc/identities") return { data: methods };
    if (path === "/api/v1/auth/config") return { data: config };
    if (path === "/api/v1/auth/me") return { data: { id: 1, display_name: "Me", email: "me@example.com" } };
    return { data: [] };
  });
}

function setup(url = "/account", go = vi.fn()) {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[url]}>
        <AuthProvider>
          <AccountPage go={go} />
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return go;
}

beforeEach(() => {
  for (const m of [get, post, del]) m.mockReset();
});

describe("AccountPage", () => {
  it("lists the password and each linked provider", async () => {
    serve({ has_password: true, identities: [linkedAuthentik] });
    setup();
    expect(await screen.findByText("Authentik")).toBeInTheDocument();
    expect(screen.getByText("me@elsewhere.test", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("Email and password")).toBeInTheDocument();
  });

  it("offers to link only the providers that are not linked yet", async () => {
    serve({ has_password: true, identities: [linkedAuthentik] });
    setup();
    expect(await screen.findByRole("button", { name: "Link Google" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Link Authentik" })).not.toBeInTheDocument();
  });

  it("starts linking and sends the browser to the address the server gives", async () => {
    serve({ has_password: true, identities: [] });
    post.mockResolvedValue({ data: { url: "/api/v1/auth/oidc/google/login?client=web&link=abc" } });
    const go = setup();
    await userEvent.click(await screen.findByRole("button", { name: "Link Google" }));
    await waitFor(() => expect(go).toHaveBeenCalledWith("/api/v1/auth/oidc/google/login?client=web&link=abc"));
    expect(post).toHaveBeenCalledWith("/api/v1/auth/oidc/{provider_id}/link", { params: { path: { provider_id: "google" } } });
  });

  it("shows why linking could not start", async () => {
    serve({ has_password: true, identities: [] });
    post.mockResolvedValue({ error: { message: "Google is already linked to your account" } });
    const go = setup();
    await userEvent.click(await screen.findByRole("button", { name: "Link Google" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("already linked");
    expect(go).not.toHaveBeenCalled();
  });

  it("asks before unlinking, then unlinks", async () => {
    serve({ has_password: true, identities: [linkedAuthentik] });
    del.mockResolvedValue({});
    setup();
    await userEvent.click(await screen.findByRole("button", { name: "Unlink Authentik" }));
    expect(del).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Yes, unlink" }));
    await waitFor(() => expect(del).toHaveBeenCalledWith("/api/v1/auth/oidc/identities/{identity_id}", { params: { path: { identity_id: 7 } } }));
  });

  it("can back out of unlinking", async () => {
    serve({ has_password: true, identities: [linkedAuthentik] });
    setup();
    await userEvent.click(await screen.findByRole("button", { name: "Unlink Authentik" }));
    await userEvent.click(screen.getByRole("button", { name: "No" }));
    expect(del).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Unlink Authentik" })).toBeInTheDocument();
  });

  it("shows the server's reason when the last way in is refused", async () => {
    serve({ has_password: false, identities: [linkedAuthentik] });
    del.mockResolvedValue({ error: { message: "This is the only way you can sign in, so it can't be unlinked." } });
    setup();
    expect(await screen.findByText(/keep at least one provider linked/)).toBeInTheDocument();
    await userEvent.click(await screen.findByRole("button", { name: "Unlink Authentik" }));
    await userEvent.click(screen.getByRole("button", { name: "Yes, unlink" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("only way you can sign in");
  });

  it("confirms a link that has just been made", async () => {
    serve({ has_password: true, identities: [linkedAuthentik] });
    setup("/account?linked=authentik");
    expect(await screen.findByRole("status")).toHaveTextContent("Authentik is now linked");
  });

  it("explains a link the provider flow turned away", async () => {
    serve({ has_password: true, identities: [] });
    setup("/account?error=already_linked");
    expect(await screen.findByRole("alert")).toHaveTextContent("already linked to a different account");
  });

  it("still lists a provider the server no longer offers, so it can be unlinked", async () => {
    serve({ has_password: true, identities: [{ ...linkedAuthentik, provider_name: null }] }, { registration: "invite", oidc: [] });
    setup();
    expect(await screen.findByText(/no longer offered/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Unlink authentik" })).toBeInTheDocument();
  });
});
