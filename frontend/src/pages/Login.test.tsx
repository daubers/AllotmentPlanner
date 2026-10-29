import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const post = vi.fn();
const get = vi.fn();
vi.mock("../api/client", () => ({
  api: { POST: (...a: unknown[]) => post(...a), GET: (...a: unknown[]) => get(...a) },
  getSession: () => null,
  setSession: vi.fn(),
  setSessionExpiredHandler: vi.fn(),
}));

import { AuthProvider } from "../auth";
import Login from "./Login";

function setup(url = "/login") {
  render(
    <MemoryRouter initialEntries={[url]}>
      <AuthProvider>
        <Login />
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("Login", () => {
  beforeEach(() => {
    post.mockReset();
    get.mockReset();
  });

  it("submits credentials to the login endpoint", async () => {
    post.mockResolvedValue({ data: { access_token: "a", refresh_token: "r", user: { id: 1 } } });
    setup();
    await userEvent.type(screen.getByLabelText("Email"), "a@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "password123");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/api/v1/auth/login", { body: { email: "a@example.com", password: "password123" } }),
    );
  });

  it("shows the server's error message", async () => {
    post.mockResolvedValue({ error: { message: "Invalid email or password" } });
    setup();
    await userEvent.type(screen.getByLabelText("Email"), "a@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "wrongwrong");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid email or password");
  });

  it("switches to registration, which asks for a name", async () => {
    setup();
    await userEvent.click(screen.getByRole("button", { name: /Need an account/ }));
    expect(screen.getByLabelText("Your name")).toBeInTheDocument();
  });

  it("asks for an invite code when registration is by invitation", async () => {
    get.mockResolvedValue({ data: { registration: "invite" } });
    setup();
    await userEvent.click(screen.getByRole("button", { name: /Need an account/ }));
    expect(await screen.findByLabelText(/Invite code/)).toBeInTheDocument();
  });

  it("does not show the invite code field when registration is open", async () => {
    get.mockResolvedValue({ data: { registration: "open" } });
    setup();
    await userEvent.click(screen.getByRole("button", { name: /Need an account/ }));
    expect(screen.queryByLabelText(/Invite code/)).not.toBeInTheDocument();
  });

  it("registers from an invite link with the code and email filled in", async () => {
    get.mockResolvedValue({ data: { registration: "invite" } });
    post.mockResolvedValue({ data: { access_token: "a", refresh_token: "r", user: { id: 2 } } });
    setup("/login?invite=abc.def&email=guest%40example.com");
    expect(screen.getByLabelText("Email")).toHaveValue("guest@example.com");
    await userEvent.type(screen.getByLabelText("Your name"), "Guest");
    await userEvent.type(screen.getByLabelText("Password"), "password123");
    await userEvent.click(screen.getByRole("button", { name: "Register" }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/api/v1/auth/register", {
        body: { email: "guest@example.com", display_name: "Guest", password: "password123", invite_code: "abc.def" },
      }),
    );
  });
});
