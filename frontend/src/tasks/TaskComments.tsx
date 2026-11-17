import { useState } from "react";
import { stamp } from "../notes/NoteList";
import { useTaskCommentActions, useTaskComments, type TaskComment } from "./comments";

const STATUS_LABEL = { todo: "To do", doing: "In progress", done: "Done" } as const;
type Status = keyof typeof STATUS_LABEL;

type Props = {
  allotmentId: number;
  taskId: number;
  canEdit: boolean;
  /** The signed-in user: only a comment's author edits it. */
  meId?: number;
  /** An owner of the allotment may delete anyone's comment. */
  isOwner?: boolean;
};

/** The full date and time, so a comment's moment is clear even when it is old. */
const when = (iso: string) =>
  `${new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric" }).format(new Date(iso))}, ${stamp(iso, false)}`;

function Item({ c, mine, canDelete, onEdit, onDelete }: {
  c: TaskComment;
  mine: boolean;
  canDelete: boolean;
  onEdit(patch: { body: string; progress: string }): Promise<unknown>;
  onDelete(): Promise<unknown>;
}) {
  const [editing, setEditing] = useState(false);
  const [body, setBody] = useState(c.body ?? "");
  const [progress, setProgress] = useState(c.progress ?? "");
  const [error, setError] = useState("");

  if (editing) {
    return (
      <li className="task-comment editing">
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            try {
              await onEdit({ body, progress });
              setEditing(false);
              setError("");
            } catch (err) {
              setError((err as Error).message);
            }
          }}
        >
          <label>
            Edit comment
            <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={3} maxLength={5000} />
          </label>
          <label>
            Progress
            <input value={progress} onChange={(e) => setProgress(e.target.value)} maxLength={80} />
          </label>
          {error && <p role="alert" className="error">{error}</p>}
          <div className="actions">
            <button type="submit">Save</button>
            <button type="button" className="secondary" onClick={() => setEditing(false)}>Cancel</button>
          </div>
        </form>
      </li>
    );
  }
  return (
    <li className="task-comment">
      <div className="note-head">
        <time dateTime={c.created_at}>{when(c.created_at!)}</time>
        <span>{c.author ?? "Someone"}</span>
        {c.edited && <span className="muted">(edited)</span>}
        {c.status && <span className={`badge status-${c.status}`}>{STATUS_LABEL[c.status as Status] ?? c.status}</span>}
        {c.progress && <span className="badge progress">{c.progress}</span>}
      </div>
      {c.body && <p className="note-body">{c.body}</p>}
      {(mine || canDelete) && (
        <div className="actions">
          {mine && <button type="button" className="link" onClick={() => setEditing(true)}>Edit</button>}
          {canDelete && (
            <button type="button" className="link" onClick={() => void onDelete().catch((err) => setError((err as Error).message))}>
              Delete
            </button>
          )}
          {error && <span role="alert" className="error">{error}</span>}
        </div>
      )}
    </li>
  );
}

/** A task's comment timeline, with a box to add one. Lives beside the task form, not inside it. */
export default function TaskComments({ allotmentId, taskId, canEdit, meId, isOwner }: Props) {
  const comments = useTaskComments(allotmentId, taskId);
  const actions = useTaskCommentActions(allotmentId, taskId);
  const [body, setBody] = useState("");
  const [status, setStatus] = useState<"" | Status>("");
  const [progress, setProgress] = useState("");
  const [error, setError] = useState("");

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (!body.trim() && !status && !progress.trim()) {
      setError("Write something, or choose a status or progress");
      return;
    }
    try {
      await actions.create.mutateAsync({ body, status: status || null, progress: progress.trim() || null });
      setBody("");
      setStatus("");
      setProgress("");
      setError("");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <section className="task-comments" aria-label="Comments">
      <h3>Comments</h3>
      {comments.data?.length === 0 && <p className="muted">No comments yet.</p>}
      <ul className="notes">
        {comments.data?.map((c) => (
          <Item
            key={c.id}
            c={c}
            mine={canEdit && meId !== undefined && c.author_id === meId}
            canDelete={canEdit && (!!isOwner || (meId !== undefined && c.author_id === meId))}
            onEdit={(body) => actions.update.mutateAsync({ id: c.id!, body })}
            onDelete={() => actions.remove.mutateAsync(c.id!)}
          />
        ))}
      </ul>
      {canEdit && (
        <form onSubmit={add} className="add-comment">
          <label>
            New comment
            <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={2} maxLength={5000} />
          </label>
          <div className="row">
            <label>
              Set status
              <select value={status} onChange={(e) => setStatus(e.target.value as "" | Status)}>
                <option value="">No change</option>
                {(Object.keys(STATUS_LABEL) as Status[]).map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
              </select>
            </label>
            <label>
              Progress
              <input value={progress} onChange={(e) => setProgress(e.target.value)} maxLength={80} placeholder="e.g. waiting on seed" />
            </label>
          </div>
          {error && <p role="alert" className="error">{error}</p>}
          <button type="submit" disabled={actions.create.isPending}>Add comment</button>
        </form>
      )}
    </section>
  );
}
