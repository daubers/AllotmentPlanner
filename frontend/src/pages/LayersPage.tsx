import { useState } from "react";
import { formatDuration } from "../media/group";
import { useMedia } from "../media/hooks";
import { useMapActions, useLayers, useMapJobDetail, useMapJobs } from "../maps/hooks";
import { anyActive, clampOpacity, defaultHeight, isActive, jobSummary, readiness, videoFrames, type MapJob } from "../maps/status";
import { useAllotment } from "./AllotmentLayout";

export default function LayersPage() {
  const { id, canEdit } = useAllotment();
  const layers = useLayers(id);
  const jobs = useMapJobs(id, canEdit);
  const media = useMedia(id); // photos and videos
  const actions = useMapActions(id);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<"oblique" | "overhead">("oblique");
  const [height, setHeight] = useState(defaultHeight("oblique"));
  const [detect, setDetect] = useState(true);
  const [overlay, setOverlay] = useState(false);
  const [choosing, setChoosing] = useState(false);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);
  const [openJob, setOpenJob] = useState<number | null>(null);

  const files = media.data ?? [];
  const readyFiles = files.filter((m) => m.status === "ready");
  const ready = readiness(files, choosing ? selected : null);
  const busy = anyActive(jobs.data);

  async function attempt(action: () => Promise<unknown>) {
    try {
      await action();
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  function build(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const name = String(new FormData(e.currentTarget).get("name") ?? "").trim();
    void attempt(() => actions.build.mutateAsync({ name, view, camera_height_m: height, detect_objects: detect, overlay, media_ids: choosing ? [...selected] : null }));
  }

  const toggle = (photoId: number) =>
    setSelected((s) => {
      const next = new Set(s);
      if (next.has(photoId)) next.delete(photoId);
      else next.add(photoId);
      return next;
    });

  return (
    <main className="page">
      <h1>From your photos</h1>
      <p className="muted">
        Walk the plot taking overlapping photos (and video) with location switched on. The app works out where each
        was taken, finds the beds, trees, sheds and other things in them, and suggests shapes and names for your map.
        Nothing reaches the map until you accept it.
      </p>
      {error && <p role="alert" className="error">{error}</p>}

      <h2>Photo overlays <span className="badge">experimental</span></h2>
      {layers.data?.length ? (
        <ul className="layer-list">
          {layers.data.map((l) => (
            <li key={l.id} className="layer">
              <div className="layer-head">
                <label className="check">
                  <input
                    type="checkbox"
                    checked={!!l.visible}
                    disabled={!canEdit}
                    onChange={(e) => void attempt(() => actions.patchLayer.mutateAsync({ id: l.id!, visible: e.target.checked }))}
                  />
                  <strong>{l.name}</strong>
                </label>
                <span className="muted">{l.tile_count} tiles</span>
              </div>
              <label className="slider">
                Opacity
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  defaultValue={l.opacity ?? 0.85}
                  disabled={!canEdit}
                  onPointerUp={(e) => void attempt(() => actions.patchLayer.mutateAsync({ id: l.id!, opacity: clampOpacity(Number(e.currentTarget.value)) }))}
                  onKeyUp={(e) => void attempt(() => actions.patchLayer.mutateAsync({ id: l.id!, opacity: clampOpacity(Number(e.currentTarget.value)) }))}
                />
              </label>
              {canEdit && (
                <div className="inline">
                  {confirmDelete === l.id ? (
                    <button type="button" className="danger" onClick={() => { setConfirmDelete(null); void attempt(() => actions.removeLayer.mutateAsync(l.id!)); }}>
                      Really delete?
                    </button>
                  ) : (
                    <button type="button" className="secondary" onClick={() => setConfirmDelete(l.id!)}>Delete</button>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">None built. Overlays are optional: recognised things are reviewed on the Map page.</p>
      )}

      {canEdit && (
        <>
          <h2>Find things in my photos</h2>
          <form className="settings-form" onSubmit={build}>
            <fieldset>
              <legend>What to make</legend>
              <label className="check">
                <input type="checkbox" checked={detect} onChange={(e) => setDetect(e.target.checked)} />
                <span><strong>Recognise things</strong>: beds, trees, sheds, water butts, compost bins. You review them before they reach the map.</span>
              </label>
              <label className="check">
                <input type="checkbox" checked={overlay} onChange={(e) => setOverlay(e.target.checked)} />
                <span><strong>Photo overlay</strong> (experimental): a stitched picture of the ground. Only works well for photos taken from directly above, and stays hidden until you switch it on.</span>
              </label>
              {!detect && !overlay && <p className="hint">Pick at least one.</p>}
            </fieldset>
            <label>
              Name
              <input name="name" placeholder="e.g. Whole plot, November" maxLength={120} />
            </label>
            <label>
              How were the photos taken?
              <select
                value={view}
                onChange={(e) => {
                  const next = e.target.value as "oblique" | "overhead";
                  setView(next);
                  setHeight(defaultHeight(next));
                }}
              >
                <option value="oblique">Hand-held, camera roughly level</option>
                <option value="overhead">From above, looking straight down (pole or drone)</option>
              </select>
            </label>
            <label>
              Camera height (metres)
              <input type="number" inputMode="decimal" min={0.3} max={120} step={0.1} value={height} onChange={(e) => setHeight(Number(e.target.value))} />
              <span className="hint">Roughly how high the camera was above the ground. Hand-held is about 1.7.</span>
            </label>
            <fieldset>
              <legend>Photos and videos</legend>
              <label className="check">
                <input type="radio" checked={!choosing} onChange={() => setChoosing(false)} /> Everything that is ready ({readyFiles.length})
              </label>
              <label className="check">
                <input type="radio" checked={choosing} onChange={() => setChoosing(true)} /> Choose which ones
              </label>
              {choosing && (
                <ul className="grid pick-grid">
                  {readyFiles.map((m) => (
                    <li key={m.id}>
                      <label className={`tile pick ${selected.has(m.id!) ? "picked" : ""}`}>
                        <input type="checkbox" checked={selected.has(m.id!)} onChange={() => toggle(m.id!)} aria-label={`Use ${m.filename}`} />
                        {m.thumb_url && <img src={m.thumb_url} alt="" loading="lazy" />}
                        {m.kind === "video" ? (
                          <span className="tile-badge">▶ {formatDuration(m.duration_s)} · {videoFrames(m)} frames</span>
                        ) : (
                          m.lat == null && <span className="no-gps">no location</span>
                        )}
                      </label>
                    </li>
                  ))}
                </ul>
              )}
              <p className="muted">
                {ready.photos} photos ({ready.located} with a location)
                {ready.videos > 0 && <>, {ready.videos} {ready.videos === 1 ? "video" : "videos"}</>}: about {ready.images} images in all.
              </p>
              {ready.problems.map((p) => <p key={p} className="hint">{p}</p>)}
              <p className="hint">
                Videos are sampled about once a second (the sharpest frame each time) and fitted in by matching them to your photos,
                so walk the plot with a video and take a few photos with location on to anchor it.
              </p>
            </fieldset>
            <div className="inline">
              <button type="submit" disabled={!ready.ok || busy || actions.build.isPending || (!detect && !overlay)}>Start</button>
              {busy && <span className="muted">A map is already being built.</span>}
            </div>
          </form>

          <h2>Recent runs</h2>
          {jobs.data?.length ? (
            <ul className="post-list">
              {jobs.data.map((j) => (
                <JobRow key={j.id} job={j} allotmentId={id} open={openJob === j.id} onToggle={() => setOpenJob(openJob === j.id ? null : j.id!)}
                  onCancel={() => void attempt(() => actions.cancel.mutateAsync(j.id!))}
                  onRemove={() => void attempt(() => actions.removeJob.mutateAsync(j.id!))} />
              ))}
            </ul>
          ) : (
            <p className="muted">Nothing run yet.</p>
          )}
        </>
      )}
    </main>
  );
}

function JobRow({ job, allotmentId, open, onToggle, onCancel, onRemove }: {
  job: MapJob; allotmentId: number; open: boolean; onToggle(): void; onCancel(): void; onRemove(): void;
}) {
  const detail = useMapJobDetail(allotmentId, open ? job.id! : null, isActive(job));
  const summary = jobSummary(job);
  return (
    <li className="post">
      <div className="post-head">
        <span className={`status ${summary.tone}`}>{summary.label}</span>
        <span className="muted">{job.name} · {job.media_count} photos</span>
      </div>
      <div className="inline">
        {isActive(job) && !job.cancel_requested && <button type="button" className="secondary" onClick={onCancel}>Cancel</button>}
        {!isActive(job) && <button type="button" className="secondary" onClick={onRemove}>Remove</button>}
        <button type="button" className="link" onClick={onToggle}>{open ? "Hide details" : "Details"}</button>
      </div>
      {open && <pre className="job-log">{detail.data?.log || "No log yet."}</pre>}
    </li>
  );
}
