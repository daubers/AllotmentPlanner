import { useEffect, useState } from "react";
import { Navigate, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth";

export default function Login() {
  const { user, login, register } = useAuth();
  const [params] = useSearchParams();
  const invite = params.get("invite") ?? "";
  const [mode, setMode] = useState<"login" | "register">(invite ? "register" : "login");
  const [inviteOnly, setInviteOnly] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void Promise.resolve(api.GET("/api/v1/auth/config")).then((r) => setInviteOnly(r?.data?.registration === "invite"));
  }, []);

  if (user) return <Navigate to="/" replace />;

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const email = String(form.get("email"));
    const password = String(form.get("password"));
    setBusy(true);
    setError(
      mode === "login"
        ? await login(email, password)
        : await register(email, String(form.get("display_name")), password, String(form.get("invite_code") ?? "").trim()),
    );
    setBusy(false);
  }

  return (
    <main className="auth">
      <h1>Allotment Planner</h1>
      <form onSubmit={submit}>
        <h2>{mode === "login" ? "Sign in" : "Create account"}</h2>
        {mode === "register" && (
          <label>
            Your name
            <input name="display_name" required maxLength={100} autoComplete="name" />
          </label>
        )}
        <label>
          Email
          <input name="email" type="email" required autoComplete="email" defaultValue={params.get("email") ?? ""} />
        </label>
        <label>
          Password
          <input name="password" type="password" required minLength={mode === "register" ? 8 : undefined} autoComplete={mode === "login" ? "current-password" : "new-password"} />
        </label>
        {mode === "register" && (inviteOnly || invite) && (
          <label>
            Invite code
            <input name="invite_code" defaultValue={invite} autoComplete="off" autoCapitalize="none" />
            <span className="hint">
              Registration here is by invitation: use the email the invite was made for. Leave the code blank only to set up the very first account.
            </span>
          </label>
        )}
        {error && <p role="alert" className="error">{error}</p>}
        <button type="submit" disabled={busy}>{mode === "login" ? "Sign in" : "Register"}</button>
        <button type="button" className="link" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(null); }}>
          {mode === "login" ? "Need an account? Register" : "Have an account? Sign in"}
        </button>
      </form>
    </main>
  );
}
