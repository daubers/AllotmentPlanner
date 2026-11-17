import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { startLink, useAuthMethods, useProviders, useUnlink } from "../account/hooks";
import { useAuth } from "../auth";
import { ssoError } from "./Login";

/** The signed-in person's own account: who they are and which ways they can sign in. */
export default function AccountPage({ go = (url: string) => window.location.assign(url) }: { go?: (url: string) => void }) {
  const { user } = useAuth();
  const [params] = useSearchParams();
  const methods = useAuthMethods();
  const providers = useProviders();
  const unlink = useUnlink();
  const [error, setError] = useState<string | null>(ssoError(params.get("error")));
  const [confirm, setConfirm] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  const linkedIds = new Set(methods.data?.identities?.map((i) => i.provider));
  const available = (providers.data ?? []).filter((p) => !linkedIds.has(p.id ?? ""));
  const justLinked = params.get("linked");
  const justLinkedName = providers.data?.find((p) => p.id === justLinked)?.name ?? justLinked;

  async function link(providerId: string) {
    setBusy(true);
    setError(null);
    try {
      go(await startLink(providerId));
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  async function remove(id: number) {
    setError(null);
    try {
      await unlink.mutateAsync(id);
      setConfirm(null);
    } catch (err) {
      setError((err as Error).message);
      setConfirm(null);
    }
  }

  return (
    <main className="page">
      <h1>Your account</h1>
      <p>
        {user?.display_name} <span className="muted">· {user?.email}</span>
      </p>

      <h2>Ways to sign in</h2>
      {justLinked && !error && providers.isFetched && <p role="status" className="ok">{justLinkedName} is now linked to your account.</p>}
      {error && <p role="alert" className="error">{error}</p>}
      {methods.isLoading && <p className="muted">Loading…</p>}
      <ul className="cards signins">
        <li>
          <span><strong>Email and password</strong></span>
          <span className="badge">{methods.data?.has_password === false ? "not set" : "set"}</span>
        </li>
        {methods.data?.identities?.map((i) => (
          <li key={i.id}>
            <span>
              <strong>{i.provider_name ?? i.provider}</strong>
              {i.email && <span className="muted"> · {i.email}</span>}
              {!i.provider_name && <span className="muted"> · no longer offered by this server</span>}
            </span>
            {confirm === i.id ? (
              <span>
                <span className="muted">Unlink?</span>{" "}
                <button type="button" className="danger" onClick={() => void remove(i.id!)} disabled={unlink.isPending}>Yes, unlink</button>{" "}
                <button type="button" className="secondary" onClick={() => setConfirm(null)}>No</button>
              </span>
            ) : (
              <button type="button" className="link" aria-label={`Unlink ${i.provider_name ?? i.provider}`} onClick={() => setConfirm(i.id!)}>
                Unlink
              </button>
            )}
          </li>
        ))}
      </ul>
      {available.length > 0 && (
        <div className="sso" role="group" aria-label="Link a provider">
          {available.map((p) => (
            <button key={p.id} type="button" className="secondary" disabled={busy} onClick={() => void link(p.id!)}>
              Link {p.name}
            </button>
          ))}
        </div>
      )}
      {methods.data?.has_password === false && (
        <p className="hint">You have no password, so keep at least one provider linked.</p>
      )}
      <p><Link to="/">Back to your allotments</Link></p>
    </main>
  );
}
