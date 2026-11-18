import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  deleteAccount,
  SharedAllotmentsError,
  startLink,
  startReauth,
  useAuthMethods,
  useExportStatus,
  useProviders,
  useRequestExport,
  useUnlink,
} from "../account/hooks";
import { useAuth } from "../auth";
import { ssoError } from "./Login";

/** The signed-in person's own account: who they are and which ways they can sign in. */
export default function AccountPage({ go = (url: string) => window.location.assign(url) }: { go?: (url: string) => void }) {
  const { user, logout } = useAuth();
  const [params] = useSearchParams();
  const methods = useAuthMethods();
  const providers = useProviders();
  const unlink = useUnlink();
  const [error, setError] = useState<string | null>(ssoError(params.get("error")));
  const [confirm, setConfirm] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const requestExport = useRequestExport();
  const [exportId, setExportId] = useState<number | null>(null);
  const exportStatus = useExportStatus(exportId);
  const [deleting, setDeleting] = useState(false);
  const [password, setPassword] = useState("");
  const [blocking, setBlocking] = useState<{ id: number; name: string }[]>([]);
  // A provider sends the person back here with a one-time code that confirms the deletion.
  const reauthCode = params.get("reauth");

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

  async function askForExport() {
    setError(null);
    try {
      setExportId((await requestExport.mutateAsync()).id ?? null);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function confirmWithProvider(providerId: string) {
    setBusy(true);
    setError(null);
    try {
      go(await startReauth(providerId));
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  async function removeAccount(proof: { password?: string; reauth_code?: string }) {
    setBusy(true);
    setError(null);
    setBlocking([]);
    try {
      await deleteAccount(proof);
      logout();
      go("/login");
    } catch (err) {
      if (err instanceof SharedAllotmentsError) setBlocking(err.allotments);
      setError((err as Error).message);
      setBusy(false);
    }
  }

  const exp = exportStatus.data;
  const hasPassword = methods.data?.has_password !== false;

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

      <h2>Your data</h2>
      <p>Download a zip with your account details, everything you added and the photos and videos you uploaded.</p>
      {(exportId === null || exp?.status === "failed" || exp?.status === "expired") && (
        <button type="button" className="secondary" disabled={requestExport.isPending} onClick={() => void askForExport()}>
          Download my data
        </button>
      )}
      {exp?.status === "pending" && <p role="status" className="muted">Preparing your data… this can take a few minutes if you have a lot of photos.</p>}
      {exp?.status === "ready" && exp.url && (
        <p role="status" className="ok">
          Your data is ready: <a href={exp.url} download>download the zip</a>. The link works for two days.
        </p>
      )}
      {exp?.status === "failed" && <p role="alert" className="error">The export failed. Please try again.</p>}
      {exp?.status === "expired" && <p className="muted">That export has expired.</p>}

      <h2>Delete account</h2>
      <p>
        This permanently deletes your account, and any allotment that only you belong to, with its photos. Things you added
        to allotments shared with others stay there, no longer linked to you.
      </p>
      {blocking.length > 0 && (
        <ul>
          {blocking.map((a) => (
            <li key={a.id}>{a.name}</li>
          ))}
        </ul>
      )}
      {reauthCode ? (
        <p>
          <span className="ok">Confirmed.</span>{" "}
          <button type="button" className="danger" disabled={busy} onClick={() => void removeAccount({ reauth_code: reauthCode })}>
            Delete my account for good
          </button>
        </p>
      ) : !deleting ? (
        <button type="button" className="danger" onClick={() => setDeleting(true)}>Delete my account…</button>
      ) : hasPassword ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void removeAccount({ password });
          }}
        >
          <label>
            Your password
            <input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </label>{" "}
          <button type="submit" className="danger" disabled={busy || !password}>Delete my account for good</button>{" "}
          <button type="button" className="secondary" onClick={() => { setDeleting(false); setPassword(""); }}>Cancel</button>
        </form>
      ) : (
        <div className="sso" role="group" aria-label="Confirm with a provider">
          <p className="muted">You have no password, so confirm it is you with a provider.</p>
          {methods.data?.identities?.map((i) => (
            <button key={i.id} type="button" className="danger" disabled={busy} onClick={() => void confirmWithProvider(i.provider!)}>
              Confirm with {i.provider_name ?? i.provider}
            </button>
          ))}{" "}
          <button type="button" className="secondary" onClick={() => setDeleting(false)}>Cancel</button>
        </div>
      )}

      <p><Link to="/">Back to your allotments</Link></p>
    </main>
  );
}
