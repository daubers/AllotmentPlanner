import { useEffect, useRef, useState } from "react";
import { compass, dayOf, formatDuration, formatSize, mapLink, timeOf, type Media } from "./group";

type Props = {
  item: Media;
  features: { id: number; name: string }[];
  canEdit: boolean;
  onClose(): void;
  onSave(patch: { caption?: string; feature_id?: number | null }): void;
  onDelete(): void;
  onRetry(): void;
};

export default function Lightbox({ item, features, canEdit, onClose, onSave, onDelete, onRetry }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const [caption, setCaption] = useState(item.caption ?? "");
  useEffect(() => {
    ref.current?.showModal();
  }, []);
  useEffect(() => setCaption(item.caption ?? ""), [item.id, item.caption]);

  const link = mapLink(item);
  const facing = compass(item.heading);
  return (
    <dialog
      ref={ref}
      className="lightbox"
      // Escape / Close go through React state (and unmount us) instead of only closing the native
      // dialog, so the two can never disagree and re-open the modal on a later render.
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onClose={onClose}
      onClick={(e) => e.target === ref.current && onClose()}
    >
      <div className="lightbox-body">
        <div className="lightbox-media">
          {item.status === "failed" ? (
            <p role="alert" className="error">Couldn't process this file: {item.error}</p>
          ) : item.kind === "video" ? (
            <video src={item.url} controls poster={item.thumb_url ?? undefined} />
          ) : (
            <img src={item.url} alt={item.caption || item.filename} />
          )}
        </div>
        <div className="lightbox-info">
          <h2>{dayOf(item)} <span className="muted">{timeOf(item)} UTC</span></h2>
          <dl>
            <dt>File</dt>
            <dd>{item.filename} · {formatSize(item.size_bytes ?? 0)}{item.width ? ` · ${item.width}×${item.height}` : ""}{item.duration_s ? ` · ${formatDuration(item.duration_s)}` : ""}</dd>
            <dt>Taken</dt>
            <dd>{item.taken_at_source === "exif" ? "from the camera" : item.taken_at_source === "manual" ? "set by hand" : "when uploaded"}</dd>
            <dt>Where</dt>
            <dd>{link ? <a href={link} target="_blank" rel="noreferrer">{item.lat!.toFixed(5)}, {item.lng!.toFixed(5)}</a> : "No location in the file"}{facing && ` · facing ${facing}`}</dd>
          </dl>
          <label>
            Caption
            <input value={caption} disabled={!canEdit} maxLength={500} onChange={(e) => setCaption(e.target.value)} onBlur={() => caption !== (item.caption ?? "") && onSave({ caption })} />
          </label>
          <label>
            Bed / feature
            <select value={item.feature_id ?? ""} disabled={!canEdit} onChange={(e) => onSave({ feature_id: e.target.value ? Number(e.target.value) : null })}>
              <option value="">None</option>
              {features.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
            </select>
          </label>
          <div className="lightbox-actions">
            {canEdit && item.status === "failed" && <button onClick={onRetry}>Retry</button>}
            {canEdit && <button className="danger" onClick={() => window.confirm("Delete this file?") && onDelete()}>Delete</button>}
            <button className="link" onClick={onClose}>Close</button>
          </div>
        </div>
      </div>
    </dialog>
  );
}
