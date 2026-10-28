import { useState } from "react";
import { useMastodon, useMastodonActions, useMastodonPosts } from "../mastodon/hooks";
import { canRetry, kindLabel, postStatus } from "../mastodon/status";
import { useAllotment } from "./AllotmentLayout";

const VISIBILITIES = [
  ["unlisted", "Unlisted: public, but kept out of public timelines"],
  ["public", "Public: shown on public timelines"],
  ["private", "Followers only"],
] as const;

export default function SettingsPage() {
  const { id, allotment } = useAllotment();
  const isOwner = allotment.role === "owner";
  const settings = useMastodon(id);
  const posts = useMastodonPosts(id);
  const actions = useMastodonActions(id);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [confirmDisconnect, setConfirmDisconnect] = useState(false);

  const s = settings.data;
  if (settings.isLoading) return <main className="page"><p className="muted">Loading…</p></main>;
  if (!s) return <main className="page"><p>Couldn't load the settings.</p></main>;

  async function run(action: () => Promise<unknown>, done: string) {
    try {
      await action();
      setError(null);
      setNotice(done);
    } catch (err) {
      setNotice(null);
      setError((err as Error).message);
    }
  }

  function save(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const text = (k: string) => String(f.get(k) ?? "").trim();
    const flag = (k: string) => f.get(k) === "on";
    void run(
      () =>
        actions.save.mutateAsync({
          instance_url: text("instance_url"),
          access_token: text("access_token") || null,
          visibility: text("visibility") as "public" | "unlisted" | "private",
          enabled: flag("enabled"),
          on_task_completed: flag("on_task_completed"),
          on_photos: flag("on_photos"),
          daily_digest: flag("daily_digest"),
        }),
      "Saved",
    );
  }

  return (
    <main className="page">
      <h1>Mastodon</h1>
      <p className="muted">
        Share progress from this allotment to a Mastodon account. Nothing is posted until you connect an account and
        switch on what to share.
        {s.configured && s.handle && <> Connected as <strong>{s.handle}</strong>.</>}
      </p>

      {isOwner ? (
        <form className="settings-form" onSubmit={save} key={`${s.instance_url}-${s.enabled}-${s.visibility}-${s.on_task_completed}-${s.on_photos}-${s.daily_digest}`}>
          <label>
            Instance
            <input name="instance_url" defaultValue={s.instance_url ?? ""} placeholder="mastodon.social" required autoCapitalize="none" />
          </label>
          <label>
            Access token
            <input
              name="access_token"
              type="password"
              autoComplete="off"
              placeholder={s.token_set ? "Saved. Leave blank to keep it" : "Paste a token with the write:statuses and write:media scopes"}
            />
            <span className="hint">
              In Mastodon: Preferences → Development → New application, with scopes <code>read:accounts</code>, <code>write:statuses</code> and{" "}
              <code>write:media</code>. The token is stored encrypted and never shown again.
            </span>
          </label>
          <label>
            Who can see posts
            <select name="visibility" defaultValue={s.visibility}>
              {VISIBILITIES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          <fieldset>
            <legend>Share</legend>
            <label className="check"><input type="checkbox" name="on_task_completed" defaultChecked={s.on_task_completed} /> When a job is finished</label>
            <label className="check"><input type="checkbox" name="on_photos" defaultChecked={s.on_photos} /> New photos (grouped, with the location removed)</label>
            <label className="check"><input type="checkbox" name="daily_digest" defaultChecked={s.daily_digest} /> A daily summary, if anything happened</label>
          </fieldset>
          <label className="check"><input type="checkbox" name="enabled" defaultChecked={s.enabled} /> <strong>Posting is on</strong></label>
          {error && <p role="alert" className="error">{error}</p>}
          {notice && <p role="status" className="ok">{notice}</p>}
          <div className="inline">
            <button type="submit" disabled={actions.save.isPending}>{s.configured ? "Save" : "Connect"}</button>
            {s.configured && (
              <>
                <button type="button" className="secondary" disabled={actions.test.isPending}
                  onClick={() => void run(() => actions.test.mutateAsync(), "Test post queued. Only you can see it")}>
                  Send test post
                </button>
                {confirmDisconnect ? (
                  <button type="button" className="danger" onClick={() => { setConfirmDisconnect(false); void run(() => actions.disconnect.mutateAsync(), "Disconnected"); }}>
                    Really disconnect?
                  </button>
                ) : (
                  <button type="button" className="secondary" onClick={() => setConfirmDisconnect(true)}>Disconnect</button>
                )}
              </>
            )}
          </div>
        </form>
      ) : (
        <p className="muted">Only the owner can change these settings.</p>
      )}

      <h2>Recent posts</h2>
      {posts.data?.length ? (
        <ul className="post-list">
          {posts.data.map((p) => {
            const st = postStatus(p);
            return (
              <li key={p.id} className="post">
                <div className="post-head">
                  <span className={`status ${st.tone}`}>{st.label}</span>
                  <span className="muted">{kindLabel(p.kind)}{p.media_count ? ` · ${p.media_count} photo${p.media_count === 1 ? "" : "s"}` : ""}</span>
                </div>
                <p className="post-text">{p.text}</p>
                {p.error && <p className="error">{p.error}</p>}
                <div className="inline">
                  {p.remote_url && <a href={p.remote_url} target="_blank" rel="noreferrer noopener">View on Mastodon</a>}
                  {isOwner && canRetry(p) && (
                    <button type="button" className="secondary" disabled={actions.retry.isPending}
                      onClick={() => void run(() => actions.retry.mutateAsync(p.id!), "Retrying")}>
                      Retry
                    </button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="muted">Nothing posted yet.</p>
      )}
    </main>
  );
}
