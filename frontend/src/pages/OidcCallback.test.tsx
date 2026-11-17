import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const post = vi.fn();
const setSession = vi.fn();
vi.mock("../api/client", () => ({
  api: { POST: (...a: unknown[]) => post(...a), GET: vi.fn() },
  getSession: () => null,
  setSession: (...a: unknown[]) => setSession(...a),
  setSessionExpiredHandler: vi.fn(),
}));

import { AuthProvider } from "../auth";
import OidcCallback from "./OidcCallback";

function setup(url: string) {
  render(
    <MemoryRouter initialEntries={[url]}>
      <AuthProvider>
        <Routes>
          <Route path="/auth/callback" element={<OidcCallback />} />
          <Route path="/" element={<p>Home</p>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("OidcCallback", () => {
  beforeEach(() => {
    post.mockReset();
    setSession.mockReset();
  });

  it("swaps the one-time code for a login, once, and goes home", async () => {
    post.mockResolvedValue({ data: { access_token: "a", refresh_token: "r", user: { id: 1 } } });
    setup("/auth/callback?code=one-time");
    expect(await screen.findByText("Home")).toBeInTheDocument();
    expect(post).toHaveBeenCalledTimes(1);
    expect(post).toHaveBeenCalledWith("/api/v1/auth/oidc/exchange", { body: { code: "one-time" } });
    expect(setSession).toHaveBeenCalledWith({ access_token: "a", refresh_token: "r" });
  });

  it("shows the server's reason when the code is refused", async () => {
    post.mockResolvedValue({ error: { message: "That sign-in code is invalid or has expired" } });
    setup("/auth/callback?code=stale");
    expect(await screen.findByRole("alert")).toHaveTextContent("invalid or has expired");
    expect(screen.getByRole("link", { name: "Back to sign in" })).toBeInTheDocument();
  });

  it("says what went wrong when the provider flow ended in an error", () => {
    setup("/auth/callback?error=email_unverified");
    expect(screen.getByRole("alert")).toHaveTextContent("has not verified");
    expect(post).not.toHaveBeenCalled();
  });

  it("does not try to sign in without a code", async () => {
    setup("/auth/callback");
    expect(screen.getByRole("alert")).toBeInTheDocument();
    await waitFor(() => expect(post).not.toHaveBeenCalled());
  });
});
