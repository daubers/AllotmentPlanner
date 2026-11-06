import { useState } from "react";
import { NoteItem } from "../notes/NoteList";
import { useNoteActions, useNotes } from "../notes/hooks";
import { groupNotesByDay } from "../notes/time";
import { longDate } from "../tasks/today";
import { useFeatureOptions } from "../tasks/hooks";
import { useAllotment } from "./AllotmentLayout";

/** Every note on every object, a day at a time. */
export default function NotesPage() {
  const { id, canEdit } = useAllotment();
  const [featureId, setFeatureId] = useState<number | "">("");
  const notes = useNotes(id, featureId === "" ? null : featureId);
  const features = useFeatureOptions(id);
  const actions = useNoteActions(id);
  const days = groupNotesByDay(notes.data ?? []);

  return (
    <div className="page wide">
      <h1>Notes</h1>
      <div className="toolbar">
        <label>
          Object{" "}
          <select value={featureId} onChange={(e) => setFeatureId(e.target.value === "" ? "" : Number(e.target.value))}>
            <option value="">All objects</option>
            {(features.data ?? []).map((f) => (
              <option key={f.id} value={f.id}>{f.name}</option>
            ))}
          </select>
        </label>
      </div>
      {notes.isPending && <p className="muted">Loading…</p>}
      {notes.data && days.length === 0 && <p className="muted">No notes yet. Click an object on the map to add one.</p>}
      {days.map((day) => (
        <section key={day.date} className="note-day">
          <h2>{longDate(day.date)}</h2>
          <ul className="notes">
            {day.items.map((n) => (
              <NoteItem
                key={n.id}
                note={n}
                canEdit={canEdit}
                showFeature
                withDay={false}
                onEdit={async (note, patch) => void (await actions.update.mutateAsync({ id: note.id!, body: patch }))}
                onDelete={async (note) => void (await actions.remove.mutateAsync(note.id!))}
              />
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
