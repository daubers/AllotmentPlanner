import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import NoteList, { AddNote } from "./NoteList";
import type { Note } from "./hooks";

const note = (over: Partial<Note> = {}): Note => ({
  id: 1,
  feature_id: 7,
  feature_name: "Bed 1",
  body: "Sowed carrots",
  noted_at: new Date("2026-11-02T09:30").toISOString(),
  author: "Owner",
  ...over,
});

describe("NoteList", () => {
  it("shows each note with its time", () => {
    render(<NoteList notes={[note(), note({ id: 2, body: "Watered", noted_at: new Date("2026-11-02T17:05").toISOString() })]} canEdit={false} onEdit={vi.fn()} onDelete={vi.fn()} />);
    expect(screen.getByText("Sowed carrots")).toBeInTheDocument();
    expect(screen.getByText("Watered")).toBeInTheDocument();
    expect(screen.getByText(/09:30/)).toBeInTheDocument();
    expect(screen.getByText(/17:05/)).toBeInTheDocument();
  });

  it("offers no editing to a viewer", () => {
    render(<NoteList notes={[note()]} canEdit={false} onEdit={vi.fn()} onDelete={vi.fn()} />);
    expect(screen.queryByRole("button", { name: "Edit" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Delete" })).toBeNull();
  });

  it("edits the text and the time", async () => {
    const onEdit = vi.fn().mockResolvedValue(undefined);
    render(<NoteList notes={[note()]} canEdit onEdit={onEdit} onDelete={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    const text = screen.getByLabelText("Note");
    await userEvent.clear(text);
    await userEvent.type(text, "Sowed parsnips");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(onEdit).toHaveBeenCalled());
    const [edited, patch] = onEdit.mock.calls[0];
    expect(edited.id).toBe(1);
    expect(patch.body).toBe("Sowed parsnips");
    expect(new Date(patch.noted_at).getTime()).toBe(new Date("2026-11-02T09:30").getTime());
  });

  it("deletes", async () => {
    const onDelete = vi.fn();
    render(<NoteList notes={[note()]} canEdit onEdit={vi.fn()} onDelete={onDelete} />);
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(onDelete).toHaveBeenCalledWith(expect.objectContaining({ id: 1 }));
  });
});

describe("AddNote", () => {
  it("adds trimmed text and clears the box, ignoring an empty note", async () => {
    const onAdd = vi.fn().mockResolvedValue(undefined);
    render(<AddNote onAdd={onAdd} />);
    await userEvent.click(screen.getByRole("button", { name: "Add note" }));
    expect(onAdd).not.toHaveBeenCalled();
    await userEvent.type(screen.getByLabelText("New note"), "  Thinned out ");
    await userEvent.click(screen.getByRole("button", { name: "Add note" }));
    expect(onAdd).toHaveBeenCalledWith("Thinned out");
    await waitFor(() => expect(screen.getByLabelText("New note")).toHaveValue(""));
  });
});
