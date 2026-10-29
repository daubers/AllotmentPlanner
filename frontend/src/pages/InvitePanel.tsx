import { useState } from "react";
import { api } from "../api/client";

type Invite = { email: string; role: string; code: string; days: number };

const ROLES = ["viewer", "editor", "owner"] as const;

/** Owner-only: make an invite for someone who has no account yet. */
export default function InvitePanel({ allotmentId }: { allotmentId: number }) {
  const [invite, setInvite] = useState<Invite | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function create(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    setBusy(true);
    const { data, error: err } = await api.POST("/api/v1/allotments/{allotment_id}/invites", {
      params: { path: { allotment_id: allotmentId } },
      body: { email: String(f.get("email")), role: String(f.get("role")) as (typeof ROLES)[number] },
    });
    setBusy(false);
    if (!data) {
      setInvite(null);
      setError((err as { message?: string } | undefined)?.message ?? "Couldn't make the invite");
      return;
    }
    setError(null);
    setInvite({ email: data.email!, role: data.role!, code: data.invite_code!, days: data.expires_in_days! });
    form.reset();
  }

  const link = invite
    ? `${window.location.origin}/login?invite=${encodeURIComponent(invite.code)}&email=${encodeURIComponent(invite.email)}`
    : "";

  return (
    <section>
      <h2>Invite someone</h2>
      <p className="muted">
        For people without an account yet. They register with this link and the same email, and join as the role you pick.
        Someone who already has an account can be added as a member instead.
      </p>
      <form className="settings-form" onSubmit={(e) => void create(e)}>
        <label>
          Their email
          <input name="email" type="email" required autoComplete="off" />
        </label>
        <label>
          Role
          <select name="role" defaultValue="viewer">
            {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </label>
        {error && <p role="alert" className="error">{error}</p>}
        <button type="submit" disabled={busy}>Make invite</button>
      </form>
      {invite && (
        <div role="status" className="ok">
          <p>
            Invite for <strong>{invite.email}</strong> as {invite.role}, valid for {invite.days} days. Send them this link:
          </p>
          <input readOnly value={link} aria-label="Invite link" onFocus={(e) => e.currentTarget.select()} />
        </div>
      )}
    </section>
  );
}
