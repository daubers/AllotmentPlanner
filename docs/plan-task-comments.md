# Plan: timestamped comments on tasks, each able to carry a status update

## Context
Tasks (`backend/allotment/models.py:177`) have a `description` and a `todo|doing|done` status, but no running commentary or history; only `completed_at/by` is stored. Notes exist only per map feature (`FeatureNote`, `models.py:148`). Users want a per-task timeline of comments, each timestamped, where a comment can also report status.

## Decisions
- A comment may carry **both**: an optional task `status` change (todo/doing/done) **and** an optional short free-text `progress` label (e.g. "waiting on seed delivery"). Either, both or neither.
- Author can edit/delete their own comment; allotment owner can delete any. Editing keeps `created_at` and shows an "edited" marker; status changes already applied are not undone.
- Web and mobile both get it.

## Backend (`backend/allotment/`)
- `models.py`: `TaskComment` modelled on `FeatureNote`: `allotment_id` (cascade, idx), `task_id` (cascade, idx), `body` Text, `status` String(10) nullable (the status set by this comment), `progress` String(80) nullable, `created_by` (SET NULL), `created_at`, `updated_at` (`_now`, tz-aware). Deleting a task cascades its comments.
- Migration `backend/migrations/versions/<new12hex>_task_comments.py`, `down_revision = "e4b17c9a5d28"` (current head), hand-written in the style of `e4b17c9a5d28_feature_notes.py`. Tests use `db.create_all()`, so keep model and migration in sync by hand.
- `schemas.py`: `TaskCommentInSchema` (body up to 5000; require at least one of body/status/progress), `TaskCommentPatchSchema`, `TaskCommentSchema` (plain Schema, `author` = display_name, like `FeatureNoteSchema`).
- `api/task_comments.py` (new blueprint, registered in `allotment/__init__.py` next to notes): `GET/POST /api/v1/allotments/<id>/tasks/<task_id>/comments`, `PATCH/DELETE .../comments/<comment_id>`. Reads `Role.VIEWER`, writes `Role.EDITOR` via `require_role` (`security.py:32`). Reuse `_get` from `api/tasks.py` for 404 across allotments.
- Status handling: when a comment includes `status`, apply it in the **same transaction** by reusing the task logic in `api/tasks.py` (`done` goes through the existing complete path incl. recurrence and `completed_at/by`; todo/doing/reopen go through the update/reopen path). Do not duplicate that logic; extract small helpers if needed. A status equal to the current one just stores the comment.
- Events: `task.comment_added/updated/deleted` via `events.emit` after commit (subject `task_id`, `comment_id`). Add `task.comment_added` to `activity.RECORDED` (`activity.py:12`). The status change itself already emits `task.completed/reopened/updated`.
- Edit rule: author only for PATCH; DELETE by author or allotment owner. Editing does not re-apply status.
- Regenerate the API contract (CI fails otherwise): `flask openapi write` -> `frontend/openapi.json`, then `npm run gen:api` in `frontend/` and `mobile/` (commands in `docs/mobile.md:9`, `README.md:87`). Commit `frontend/openapi.json` and both `schema.d.ts`.

## Web (`frontend/src/`)
- `tasks/comments.ts`: `useTaskComments(allotmentId, taskId)` and `useTaskCommentActions`, modelled on `notes/hooks.ts`; key `["task-comments", allotmentId, taskId]`; a comment with `status` also invalidates `["tasks", allotmentId]` and the todo/day-list queries (as `useTaskActions` does, `tasks/hooks.ts:53`).
- `tasks/TaskComments.tsx`: timeline list (reuse `stamp()` from `notes/NoteList.tsx:15`, author, body, status chip + progress label, "edited") and an add form (textarea, optional status select, optional progress input). Render inside `TaskDialog.tsx` when editing an existing task. The dialog is a `<form>`, so the add-comment control must be a separate form or `type="button"`.
- Styles in `index.css` near `.notes`.

## Mobile (`mobile/`)
- `src/tasks/comments.ts` hook (query via `api.GET`; post via the offline queue like `completeRequest` in `src/tasks/model.ts`, with optimistic `setQueryData` as in `useTick`, plus a handler in `src/queue/handlers.ts` and a test).
- Add a Comments `Section` to `app/tasks/[id].tsx` using `ui/kit` (`Card`, `Field`, `Button`, `T`).

## Tests
- `backend/tests/test_task_comments.py` modelled on `test_notes.py`: create/list order, edit/delete rules (author, owner, other editor 403, viewer 403, stranger 404), validation, status change applies (done completes and sets completed_by, recurrence still works), cross-allotment 404, cascade on task delete, events.
- `frontend/src/tasks/TaskComments.test.tsx` (api-mock pattern from `TaskDialog.test.tsx:6-17`); mobile jest for the handler/model; extend `e2e/tests/map-and-tasks.spec.ts` after line 122.

## Verification
`make test`; `cd frontend && npm test && npm run lint`; `cd mobile && npm test`; `git diff --exit-code` on the generated schema files; run the stack, open a task, add a comment with status "doing" then "done", and confirm the task list reflects it and timestamps show.