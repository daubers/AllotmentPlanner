import { useRef, useState } from "react";
import CompareSlider from "../media/CompareSlider";
import { dayOf, formatDuration, formatSize, groupByDay, type Media } from "../media/group";
import { uploadMedia, useMedia, useMediaActions, type MediaFilters } from "../media/hooks";
import { useUploadLimit } from "../media/limits";
import { checkFileSize } from "../media/upload";
import Lightbox from "../media/Lightbox";
import { longDate } from "../tasks/today";
import { useFeatureOptions } from "../tasks/hooks";
import { useAllotment } from "./AllotmentLayout";

type Upload = { name: string; size: number; state: "uploading" | "done" | "error"; progress?: number; message?: string };

export default function PhotosPage() {
  const { id, canEdit } = useAllotment();
  const [filters, setFilters] = useState<MediaFilters>({});
  const media = useMedia(id, filters);
  const features = useFeatureOptions(id);
  const actions = useMediaActions(id);
  const [uploads, setUploads] = useState<Upload[]>([]);
  const maxBytes = useUploadLimit();
  const [attachTo, setAttachTo] = useState<number | "">("");
  const [openId, setOpenId] = useState<number | null>(null);
  const [comparing, setComparing] = useState(false);
  const [beforeId, setBeforeId] = useState<number | null>(null);
  const [afterId, setAfterId] = useState<number | null>(null);
  const input = useRef<HTMLInputElement>(null);

  const items = media.data ?? [];
  const days = groupByDay(items);
  const open = items.find((m) => m.id === openId);
  const photos = items.filter((m) => m.kind === "photo" && m.status === "ready").sort((a, b) => dayOf(a).localeCompare(dayOf(b)) || a.id! - b.id!);
  const before = photos.find((m) => m.id === beforeId) ?? photos[0];
  const after = photos.find((m) => m.id === afterId) ?? photos[photos.length - 1];

  async function onFiles(files: FileList | null) {
    if (!files?.length) return;
    const list = [...files];
    setUploads(list.map((f) => ({ name: f.name, size: f.size, state: "uploading", progress: 0 })));
    for (const [i, file] of list.entries()) {
      const set = (u: Partial<Upload>) => setUploads((all) => all.map((x, j) => (j === i ? { ...x, ...u } : x)));
      const tooBig = checkFileSize(file, maxBytes); // say so now, rather than send gigabytes to be refused
      if (tooBig) {
        set({ state: "error", message: tooBig });
        continue;
      }
      try {
        await uploadMedia(id, { file, featureId: attachTo === "" ? null : attachTo }, (progress) => set({ progress }), maxBytes);
        set({ state: "done", progress: 1 });
      } catch (err) {
        set({ state: "error", message: (err as Error).message });
      }
    }
    actions.refresh();
    if (input.current) input.current.value = "";
  }

  const tile = (m: Media) => (
    <li key={m.id}>
      <button className="tile" onClick={() => setOpenId(m.id!)} aria-label={`Open ${m.caption || m.filename}`}>
        {m.thumb_url ? (
          <img src={m.thumb_url} alt={m.caption || m.filename} loading="lazy" />
        ) : (
          <span className={`tile-empty ${m.status}`}>{m.status === "failed" ? "⚠ failed" : m.status === "pending" ? "processing…" : m.kind === "video" ? "🎞" : "🖼"}</span>
        )}
        {m.kind === "video" && <span className="tile-badge">▶ {formatDuration(m.duration_s)}</span>}
        {m.lat != null && <span className="tile-pin" title="Has a location">📍</span>}
      </button>
    </li>
  );

  return (
    <main className="page wide">
      <h1>Photos &amp; videos</h1>
      {canEdit ? (
        <section className="upload" aria-label="Upload">
          <label className="upload-pick">
            <input ref={input} type="file" multiple accept="image/jpeg,image/png,image/webp,image/gif,video/mp4,video/quicktime,video/webm" onChange={(e) => onFiles(e.target.files)} aria-label="Choose photos or videos" />
          </label>
          <label>
            Attach to
            <select value={attachTo} onChange={(e) => setAttachTo(e.target.value ? Number(e.target.value) : "")} aria-label="Attach new uploads to">
              <option value="">Nothing in particular</option>
              {features.data?.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
            </select>
          </label>
          {uploads.length > 0 && (
            <ul className="upload-status" aria-live="polite">
              {uploads.map((u, i) => (
                <li key={i} className={u.state}>
                  {u.state === "uploading" ? "⏳" : u.state === "done" ? "✓" : "✕"} {u.name}
                  {u.state === "uploading" && u.size > 1024 * 1024 && ` — ${Math.round((u.progress ?? 0) * 100)}% of ${formatSize(u.size)}`}
                  {u.message && ` — ${u.message}`}
                  {u.state === "uploading" && u.size > 1024 * 1024 && <progress value={u.progress ?? 0} max={1} aria-label={`Uploading ${u.name}`} />}
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : (
        <p className="muted">View only: ask an owner for editor access to upload.</p>
      )}

      <div className="media-filters">
        <label>
          Show
          <select value={filters.featureId ?? ""} aria-label="Filter by feature" onChange={(e) => setFilters({ ...filters, featureId: e.target.value ? Number(e.target.value) : undefined })}>
            <option value="">Everything</option>
            {features.data?.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
          </select>
        </label>
        <label>
          Type
          <select value={filters.kind ?? ""} aria-label="Filter by type" onChange={(e) => setFilters({ ...filters, kind: (e.target.value || undefined) as MediaFilters["kind"] })}>
            <option value="">Photos and videos</option>
            <option value="photo">Photos</option>
            <option value="video">Videos</option>
          </select>
        </label>
        {photos.length >= 2 && (
          <button className="link" onClick={() => setComparing(!comparing)}>{comparing ? "Hide comparison" : "Compare over time"}</button>
        )}
      </div>

      {comparing && before && after && (
        <section className="compare-panel">
          <div className="compare-pickers">
            <label>Before
              <select value={before.id} onChange={(e) => setBeforeId(Number(e.target.value))}>
                {photos.map((p) => <option key={p.id} value={p.id}>{dayOf(p)} · {p.caption || p.filename}</option>)}
              </select>
            </label>
            <label>After
              <select value={after.id} onChange={(e) => setAfterId(Number(e.target.value))}>
                {photos.map((p) => <option key={p.id} value={p.id}>{dayOf(p)} · {p.caption || p.filename}</option>)}
              </select>
            </label>
          </div>
          <CompareSlider before={before} after={after} />
        </section>
      )}

      {media.isLoading && <p className="muted">Loading…</p>}
      {media.data && items.length === 0 && <p className="muted">Nothing here yet. Add a photo to start your progress record 📷</p>}
      {days.map((day) => (
        <section key={day.date} className="day">
          <h2>{longDate(day.date)} <span className="muted">({day.items.length})</span></h2>
          <ul className="grid">{day.items.map(tile)}</ul>
        </section>
      ))}

      {open && (
        <Lightbox
          item={open}
          features={features.data ?? []}
          canEdit={canEdit}
          onClose={() => setOpenId(null)}
          onSave={(patch) => actions.patch.mutate({ id: open.id!, ...patch })}
          onDelete={() => actions.remove.mutate(open.id!, { onSuccess: () => setOpenId(null) })}
          onRetry={() => actions.reprocess.mutate(open.id!)}
        />
      )}
    </main>
  );
}
