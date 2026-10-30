import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
const session = { current: null as null | object };
vi.mock("../api/client", () => ({
  api: { POST: vi.fn(), GET: (...a: unknown[]) => get(...a) },
  getSession: () => session.current,
  setSession: vi.fn(),
  setSessionExpiredHandler: vi.fn(),
}));

import App from "../App";
import { AuthProvider } from "../auth";
import { TOPICS } from "../help/content";

function visit(path: string) {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[path]}>
        <AuthProvider>
          <App />
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function config(registration: "open" | "invite") {
  get.mockImplementation((url: string) => {
    if (url === "/api/v1/auth/config") return Promise.resolve({ data: { registration } });
    if (url === "/api/v1/auth/me") return Promise.resolve({ data: { id: 1, display_name: "Sam" } });
    return Promise.resolve({ data: [] });
  });
}

describe("public pages", () => {
  beforeEach(() => {
    get.mockReset();
    session.current = null;
  });

  it("shows the landing page, not the login form, to a visitor at /", async () => {
    config("open");
    visit("/");
    expect(await screen.findByRole("heading", { name: /Your allotment, on one map/ })).toBeInTheDocument();
    expect(screen.queryByLabelText("Password")).not.toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Sign in" }).length).toBeGreaterThan(0);
  });

  it("offers Create account only when registration is open", async () => {
    config("open");
    visit("/");
    await waitFor(() => expect(screen.getAllByRole("link", { name: "Create account" }).length).toBeGreaterThan(0));
  });

  it("says accounts are by invitation when they are", async () => {
    config("invite");
    visit("/");
    expect(await screen.findByText(/by invitation/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Create account" })).not.toBeInTheDocument();
  });

  it("still shows a signed-in person their allotments at /", async () => {
    session.current = { access_token: "a", refresh_token: "r" };
    config("open");
    visit("/");
    expect(await screen.findByRole("heading", { name: "Your allotments" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /on one map/ })).not.toBeInTheDocument();
  });

  it("serves the privacy page without signing in, with a contact address", async () => {
    config("open");
    visit("/privacy");
    expect(await screen.findByRole("heading", { name: "Privacy", level: 1 })).toBeInTheDocument();
    expect(screen.getAllByRole("link").some((a) => a.getAttribute("href")?.startsWith("mailto:"))).toBe(true);
  });

  it("serves the help index and every topic page without signing in", async () => {
    config("open");
    visit("/help");
    expect(await screen.findByRole("heading", { name: "Help", level: 1 })).toBeInTheDocument();
    for (const t of TOPICS) expect(screen.getAllByRole("link", { name: t.title }).length).toBeGreaterThan(0);
  });

  it.each(TOPICS.map((t) => [t.slug, t.title]))("renders the %s topic", async (slug, title) => {
    config("open");
    visit(`/help/${slug}`);
    expect(await screen.findByRole("heading", { name: title, level: 1 })).toBeInTheDocument();
  });

  it("falls back to the index for a topic that does not exist", async () => {
    config("open");
    visit("/help/no-such-thing");
    expect(await screen.findByRole("heading", { name: "Help", level: 1 })).toBeInTheDocument();
  });

  it("keeps topic slugs unique", () => {
    expect(new Set(TOPICS.map((t) => t.slug)).size).toBe(TOPICS.length);
  });
});
