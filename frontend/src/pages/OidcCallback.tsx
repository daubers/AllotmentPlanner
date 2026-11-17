import { useEffect, useRef, useState } from "react";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth";
import { ssoError } from "./Login";

/** Where single sign-on ends: the provider flow sends the browser here with a one-time code. */
export default function OidcCallback() {
  const { user, oidcLogin } = useAuth();
  const [params] = useSearchParams();
  const code = params.get("code");
  const sent = useRef(false); // React runs effects twice in development; a code only works once
  const [error, setError] = useState<string | null>(ssoError(params.get("error")) ?? (code ? null : ssoError("failed")));

  useEffect(() => {
    if (!code || sent.current) return;
    sent.current = true;
    void oidcLogin(code).then(setError);
  }, [code, oidcLogin]);

  if (user) return <Navigate to="/" replace />;
  return (
    <main className="auth">
      <h1><Link to="/" className="plain">Allotment Planner</Link></h1>
      {error ? (
        <>
          <p role="alert" className="error">{error}</p>
          <Link to="/login">Back to sign in</Link>
        </>
      ) : (
        <p className="muted centre" role="status">Signing you in…</p>
      )}
    </main>
  );
}
