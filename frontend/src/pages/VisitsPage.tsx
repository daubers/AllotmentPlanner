import { useState } from "react";
import { useAllotment } from "./AllotmentLayout";
import { downloadVisitIcs, googleCalendarUrl, useCalendarToken, useVisitActions, useVisits, type Visit } from "../visits/hooks";
import VisitDialog from "../visits/VisitDialog";

function CalendarMenu({ allotmentId, visit }: { allotmentId: number; visit: Visit }) {
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <span className="calendar-menu">
      <button type="button" className="link" onClick={() => setOpen((v) => !v)}>
        Add to calendar
      </button>
      {open && (
        <span className="calendar-menu-options">
          <button
            type="button"
            className="link"
            onClick={() => {
              downloadVisitIcs(allotmentId, visit).catch((err) => setError((err as Error).message));
            }}
          >
            Download .ics (Apple/Fastmail)
          </button>
          <a className="link" href={googleCalendarUrl(visit)} target="_blank" rel="noreferrer">
            Add to Google Calendar
          </a>
        </span>
      )}
      {error && <span role="alert" className="error">{error}</span>}
    </span>
  );
}

function SubscribePanel({ allotmentId, canEdit }: { allotmentId: number; canEdit: boolean }) {
  const feed = useCalendarToken(allotmentId);
  const [copied, setCopied] = useState(false);
  const url = feed.data?.feed_url;

  async function copy() {
    if (!url) return;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard unavailable: the field below is still selectable */
    }
  }

  return (
    <details className="subscribe-panel">
      <summary>Subscribe to all visits</summary>
      <p className="muted">
        Subscribing shows every upcoming (and recent) visit in your calendar app, updating automatically.
        Google can take a few hours to notice changes; Apple and Fastmail are usually quicker.
      </p>
      {url ? (
        <>
          <input readOnly value={url} onFocus={(e) => e.currentTarget.select()} />
          <button type="button" className="secondary" onClick={() => void copy()}>
            {copied ? "Copied!" : "Copy link"}
          </button>
        </>
      ) : (
        <p className="muted">No feed yet.</p>
      )}
      {canEdit && (
        <div className="inline">
          <button type="button" className="secondary" onClick={() => feed.rotate.mutate()} disabled={feed.rotate.isPending}>
            {url ? "Rotate link" : "Create link"}
          </button>
          {url && (
            <button type="button" className="danger" onClick={() => feed.disable.mutate()} disabled={feed.disable.isPending}>
              Turn off
            </button>
          )}
        </div>
      )}
    </details>
  );
}

export default function VisitsPage() {
  const { id, canEdit } = useAllotment();
  const visits = useVisits(id);
  const actions = useVisitActions(id);
  const [dialog, setDialog] = useState<Visit | "new" | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function remove(visitId: number) {
    try {
      await actions.remove.mutateAsync(visitId);
      setConfirmDelete(null);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <main className="page visits-page">
      <div className="page-head">
        <h1>Visits</h1>
        {canEdit && <button type="button" onClick={() => setDialog("new")}>Plan a visit</button>}
      </div>
      <SubscribePanel allotmentId={id} canEdit={canEdit} />
      {error && <p role="alert" className="error">{error}</p>}
      {visits.isLoading && <p className="muted">Loading…</p>}
      {visits.data?.length === 0 && <p className="muted">No visits planned yet.</p>}
      <ul className="visits">
        {(visits.data ?? []).map((v) => (
          <li key={v.id} className="visit">
            <div className="visit-head">
              <strong>{v.title}</strong>
              <span className="muted">
                {new Date(v.starts_at!).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}
                {" · "}
                {v.duration_minutes} min
              </span>
            </div>
            {v.notes && <p>{v.notes}</p>}
            {v.task_ids && v.task_ids.length > 0 && (
              <p className="muted">
                {v.task_ids.length} task{v.task_ids.length === 1 ? "" : "s"} pegged
              </p>
            )}
            <div className="visit-actions">
              <CalendarMenu allotmentId={id} visit={v} />
              {canEdit && (
                <>
                  <button type="button" className="link" onClick={() => setDialog(v)}>Edit</button>
                  {confirmDelete === v.id ? (
                    <button type="button" className="danger" onClick={() => void remove(v.id!)}>
                      Really delete?
                    </button>
                  ) : (
                    <button type="button" className="link" onClick={() => setConfirmDelete(v.id!)}>Delete</button>
                  )}
                </>
              )}
            </div>
          </li>
        ))}
      </ul>
      {dialog && <VisitDialog allotmentId={id} visit={dialog} onClose={() => setDialog(null)} />}
    </main>
  );
}
