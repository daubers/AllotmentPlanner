import { useEffect, useState } from "react";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth";

/** What to say when single sign-on sends someone back with `?error=`. */
export const SSO_ERRORS: Record<string, string> = {
  not_invited: "There is no account for that address. Ask for an invite, then sign in with the same email.",
  email_unverified: "The provider has not verified that email address, so it can't be used to sign in.",
  no_email: "The provider did not share an email address.",
  denied: "Sign-in was cancelled or refused at the provider.",
  expired: "That sign-in took too long. Please try again.",
  invalid_state: "That sign-in could not be completed in this browser. Please try again.",
  provider_unreachable: "The sign-in provider could not be reached. Try again in a moment.",
  already_linked: "That login at the provider is already linked to a different account here.",
  provider_already_linked: "You already have a login linked from that provider. Unlink it first to use another.",
  link_expired: "That link request took too long. Please try again.",
  invalid_id_token: "The provider's reply could not be checked. Please try again.",
  token_exchange_failed: "The provider refused the sign-in. Please try again.",
};
export const ssoError = (code: string | null): string | null =>
  code ? (SSO_ERRORS[code] ?? "Sign-in failed. Please try again.") : null;

export default function Login() {
  const { user, login, register } = useAuth();
  const [params] = useSearchParams();
  const invite = params.get("invite") ?? "";
  const [mode, setMode] = useState<"login" | "register">(invite || params.get("register") ? "register" : "login");
  const [inviteOnly, setInviteOnly] = useState(false);
  const [providers, setProviders] = useState<{ id?: string; name?: string }[]>([]);
  const [error, setError] = useState<string | null>(ssoError(params.get("error")));
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void Promise.resolve(api.GET("/api/v1/auth/config")).then((r) => {
      setInviteOnly(r?.data?.registration === "invite");
      setProviders(r?.data?.oidc ?? []);
    });
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
      <h1><Link to="/" className="plain">Allotment Planner</Link></h1>
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
        {providers.length > 0 && (
          <div className="sso" role="group" aria-label="Single sign-on">
            <span className="hint">or</span>
            {providers.map((p) => (
              <a
                key={p.id}
                className="button secondary"
                href={`/api/v1/auth/oidc/${encodeURIComponent(p.id ?? "")}/login?client=web${invite ? `&invite=${encodeURIComponent(invite)}` : ""}`}
              >
                Sign in with {p.name}
              </a>
            ))}
          </div>
        )}
        <button type="button" className="link" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(null); }}>
          {mode === "login" ? "Need an account? Register" : "Have an account? Sign in"}
        </button>
      </form>
      <p className="hint legal">
        By creating an account you agree to how your data is handled on the <Link to="/privacy">privacy page</Link>. <Link to="/help">Help</Link>
      </p>
    </main>
  );
}
