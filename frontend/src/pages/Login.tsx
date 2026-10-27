import { useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth";

export default function Login() {
  const { user, login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

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
        : await register(email, String(form.get("display_name")), password),
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
          <input name="email" type="email" required autoComplete="email" />
        </label>
        <label>
          Password
          <input name="password" type="password" required minLength={mode === "register" ? 8 : undefined} autoComplete={mode === "login" ? "current-password" : "new-password"} />
        </label>
        {error && <p role="alert" className="error">{error}</p>}
        <button type="submit" disabled={busy}>{mode === "login" ? "Sign in" : "Register"}</button>
        <button type="button" className="link" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(null); }}>
          {mode === "login" ? "Need an account? Register" : "Have an account? Sign in"}
        </button>
      </form>
    </main>
  );
}
