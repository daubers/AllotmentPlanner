import { useState } from "react";
import type { Note } from "./hooks";
import { fromInput, timeOfNote, toInput } from "./time";

type Props = {
  notes: Note[];
  canEdit: boolean;
  /** Show which feature each note is on (the all-notes page). */
  showFeature?: boolean;
  onEdit(note: Note, patch: { body: string; noted_at: string }): Promise<void> | void;
  onDelete(note: Note): Promise<void> | void;
};

/** A stamp such as "2 Nov, 09:30", or just the time when the page already shows the day. */
export function stamp(iso: string, withDay: boolean): string {
  const time = timeOfNote(iso);
  if (!withDay) return time;
  return `${new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short" }).format(new Date(iso))}, ${time}`;
}

export function NoteItem({ note, canEdit, showFeature, withDay, onEdit, onDelete }: Omit<Props, "notes"> & { note: Note; withDay: boolean }) {
  const [editing, setEditing] = useState(false);
  const [body, setBody] = useState(note.body ?? "");
  const [when, setWhen] = useState(toInput(note.noted_at!));
  const [error, setError] = useState("");

  if (editing) {
    return (
      <li className="note editing">
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            if (!body.trim() || !when) return;
            try {
              await onEdit(note, { body: body.trim(), noted_at: fromInput(when) });
              setEditing(false);
              setError("");
            } catch (err) {
              setError((err as Error).message);
            }
          }}
        >
          <textarea aria-label="Note" value={body} onChange={(e) => setBody(e.target.value)} rows={3} maxLength={5000} />
          <input type="datetime-local" aria-label="When" value={when} onChange={(e) => setWhen(e.target.value)} required />
          {error && <p className="error">{error}</p>}
          <div className="note-actions">
            <button type="submit">Save</button>
            <button type="button" className="secondary" onClick={() => { setEditing(false); setBody(note.body ?? ""); setWhen(toInput(note.noted_at!)); setError(""); }}>Cancel</button>
          </div>
        </form>
      </li>
    );
  }
  return (
    <li className="note">
      <div className="note-head">
        <time dateTime={note.noted_at}>{stamp(note.noted_at!, withDay)}</time>
        {showFeature && <span className="note-feature">{note.feature_name}</span>}
        {note.author && <span className="muted">{note.author}</span>}
      </div>
      <p className="note-body">{note.body}</p>
      {canEdit && (
        <div className="note-actions">
          <button type="button" className="secondary" onClick={() => setEditing(true)}>Edit</button>
          <button type="button" className="secondary" onClick={() => void onDelete(note)}>Delete</button>
        </div>
      )}
    </li>
  );
}

/** A feature's notes, newest first, each with its time and (for editors) Edit and Delete. */
export default function NoteList({ notes, ...rest }: Props) {
  return (
    <ul className="notes">
      {notes.map((n) => (
        <NoteItem key={n.id} note={n} withDay {...rest} />
      ))}
    </ul>
  );
}

/** The add-a-note form. */
export function AddNote({ onAdd }: { onAdd(body: string): Promise<void> | void }) {
  const [body, setBody] = useState("");
  return (
    <form
      className="note-add"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!body.trim()) return;
        const text = body.trim();
        setBody(""); // at once: anything typed while it saves must not be wiped afterwards
        await onAdd(text);
      }}
    >
      <textarea aria-label="New note" placeholder="Add a note" value={body} onChange={(e) => setBody(e.target.value)} rows={2} maxLength={5000} />
      <button type="submit">Add note</button>
    </form>
  );
}
