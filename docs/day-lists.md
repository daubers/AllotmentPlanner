# Day lists: pick tasks into named lists, then a todo sheet (print or in the app)

Status: planned, not built yet.

## Context
Today builds its sheet automatically from "everything due on or before a date". There is no way to hand-pick what to do
(e.g. "Saturday morning", "Watering round") and print or tick off just that. Chosen with the user: saved, several named
lists per allotment; tasks are picked from the Tasks page, from the Today page and with a quick "add to list" button on
each task, where "add to today" means "add to the selected list". "Tickets" = tasks in the app (not YouTrack).

What exists: `GET /allotments/<id>/todo` (`backend/allotment/api/todo.py`, `TodoSchema`) feeds the Today sheet
(`frontend/src/pages/TodayPage.tsx`: `Sheet`, interactive tick boxes, print CSS, `tasks/today.ts` `groupByLocation`/`flatten`,
sketch map). Tasks page (`pages/TasksPage.tsx`) has Select mode with a bulk bar (`POST /tasks/bulk`). `components/Modal.tsx`,
`tasks/hooks.ts` (`useTaskActions`, `useTodo`) and the `require_role` pattern are reusable.

## Approach

### 1. Backend (ticket A)
- Models + migration (new head after `c29f5d1a7e36`): `DayList` (allotment_id, name, optional `date`, created_by, created_at)
  and `DayListItem` (list_id, task_id, added_at; unique list+task; both FKs `CASCADE`, so deleting a task or list tidies up).
- New `api/day_lists.py` (`/api/v1/allotments/<id>/day-lists`): `GET` (viewer; each list with `task_ids`, `task_count`,
  `done_count`), `POST` (editor), `GET/PATCH/DELETE /<list_id>`, `POST /<list_id>/tasks {task_ids}` (idempotent, all ids must
  belong to this allotment else 422, all-or-nothing, editors), `DELETE /<list_id>/tasks/<task_id>`, and
  `GET /<list_id>/todo` returning the same `TodoSchema` as `/todo` but with the list's tasks (done ones included, so a ticked job
  stays on the sheet), date = list date or today. Reuse `task_to_dict`, `feature_to_geojson`, the priority sort from `api/todo.py`.
- Events (`events.emit`) for create/add like other endpoints. Tests in new `tests/test_day_lists.py`: roles (viewer reads,
  editor writes, non-member 404), foreign task 422, idempotent add, remove, task deletion cascades, sheet includes done tasks,
  empty list.

### 2. Lists and sheet in the web app (ticket A)
- `tasks/dayLists.ts` hooks: `useDayLists`, `useDayListSheet`, actions (create, rename, delete, add tasks, remove task), all
  invalidating lists and `/todo`; `useSelectedList(allotmentId)` remembers the chosen list in localStorage (per allotment, with a
  safe fallback) - this is the "selected list" the quick-add buttons use.
- `TodayPage.tsx`: a list switcher (Everything due / each list / + New list) in the controls row, in the URL as `?list=<id>`.
  With a list chosen the same `Sheet` renders from `useDayListSheet` (title shows the list name; on screen each job gets a
  remove ✕ that is hidden in print; ticking still completes; print keeps the empty boxes). A "Manage lists" modal (new
  `tasks/DayListsDialog.tsx`, built on `Modal`) creates, renames (with optional date) and deletes lists, with an in-dialog confirm.
- "Plan this list" panel on Today (`<details>`, no-print): all open tasks with checkboxes and the existing `filterTasks` search,
  "Add N to list".

### 3. Picking from the Tasks page and quick add (ticket B)
- `TasksPage.tsx`: the Select-mode bulk bar gets "Add to list" (a `<select>` of lists + "New list…", defaulting to the selected
  list); each row gets a small "+ List" button that adds to the selected list in one click (long-press/menu to choose another)
  and a chip showing which lists it is on, e.g. "Sat". New small `tasks/ListMenu.tsx` shared by both.
- Task dialog (`TaskDialog.tsx`): shows the lists the task is on, with add/remove.
- Rows on a list from Today link back to the task dialog as before.

### 4. Not in this round
Reordering inside a list (the sheet stays grouped by bed/tray as today), sharing/printing several lists at once, phone app
(the list is visible there only via Today's data later), recurring lists. Help text (`help/content.tsx`) is updated.

## Workflow
Two tickets under epic AM-48, one branch each, merged `--no-ff` to `main`, commented and set to **Review**; no release until
asked. Ticket A: backend + lists + Today sheet. Ticket B: pick from Tasks page / quick add / task dialog.

## Verification
- Backend: `docker compose run --rm -v "$PWD/backend:/app" api sh -c "ruff check . && ruff format --check . && pytest -q"`;
  `flask db upgrade` for the new migration; regenerate OpenAPI and `npm run gen:api` in `frontend/` and `mobile/`.
- Web: `tsc --noEmit`, `vitest run` (new: DayListsDialog, Today with a list incl. remove and tick, Tasks add-to-list and bulk
  add, hooks fallback when localStorage is blocked), `npm run build`.
- Playwright: extend `e2e/tests/map-and-tasks.spec.ts` (create a list, add two tasks from the Tasks page, open the sheet on
  Today, tick one); screenshots of Today with a list, the Manage dialog and the Tasks page on desktop, a 390px phone and dark
  mode. Clean up any `e2e-*` users/allotments left in the dev DB by id only.
