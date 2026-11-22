# Plan: Allotment visits with pegged tasks and calendar export

## Context
Users want to plan an allotment visit, attach a list of tasks to it, and add the visit to Google, Apple or Fastmail calendars. The app lives in `/Users/matt/PycharmProjects/AllotmentPlanner` (this AllotmentDeploy repo is only Ansible and gets no changes). No visit, ICS or email concept exists yet. `DayList` (named, hand-picked task list with optional date) is the nearest thing, but it has no start time or duration, so a new `Visit` model is used. Tasks keep their own lifecycle; a visit only links to them.

## Backend (`backend/`)
- **Models** (`allotment/models.py`, near `Task`/`DayList`, same typed `Mapped` style):
  - `Visit`: `id`, `allotment_id`, `title`, `notes`, `starts_at` (tz-aware datetime), `duration_minutes` (default 120), `created_by`, timestamps.
  - `VisitTask`: association (`visit_id`, `task_id`, unique pair, `position`), cascade on delete. Model on `DayListItem`.
  - `Allotment.calendar_token` (random, nullable, rotatable) for the feed.
- **Migration**: new file in `migrations/versions/` after head `i4f16a8e2d93_account_exports`.
- **API** `allotment/api/visits.py`, registered like `day_lists.py`, under `/api/v1/allotments/<id>/visits`:
  - CRUD, `POST /<visit_id>/tasks` (add, accepts a list of task ids), `DELETE /<visit_id>/tasks/<task_id>`.
  - `GET /<visit_id>/calendar.ics`: single-event download (JWT auth; viewer+ role via `require_role`).
  - `GET/POST/DELETE /calendar-token`: owner/editor creates or rotates the feed token.
  - Public `GET /api/v1/calendar/<token>.ics`: VCALENDAR feed of all the allotment's upcoming and recent visits, no JWT, token is the secret.
- **ICS generation** `allotment/ics.py`: add the `icalendar` dependency to `pyproject.toml`. VEVENT with stable `UID` (`visit-<id>@<host from PUBLIC_URL>`), `DTSTAMP`, `DTSTART/DTEND` in UTC, `SEQUENCE` from `updated_at` so feed edits propagate, `SUMMARY`, `DESCRIPTION` (notes plus a checklist of task titles) and `URL` back to the visit in the app (`PUBLIC_URL`). Add a `VALARM` for a 1 hour reminder.
- Tasks: reuse existing schemas/serialisation from `api/tasks.py` for visit detail. Completing a task is unchanged.

## Web (`frontend/src`)
- `visits/` module mirroring `tasks/`: `hooks.ts`, `VisitDialog.tsx` (title, date/time, duration, notes, multi-select task picker reusing task filter/group helpers), and a `VisitsPage.tsx` plus route in `App.tsx`.
- "Add to calendar" menu on a visit: Download .ics (Apple/Fastmail), Google Calendar prefilled link (`calendar.google.com/calendar/render?action=TEMPLATE&...`), and "Subscribe" showing the `webcal://` feed URL with copy and rotate buttons.
- Regenerate the API client: update `openapi.json` and run `npm run gen:api`.

## Mobile (`mobile/`)
- `src/visits/` plus `app/visits/` screens (list, new, detail) following `app/tasks/*`.
- Add-to-calendar: share/open the `.ics` via `expo-file-system` + `expo-sharing` (opens in any calendar app), plus a copy-feed-URL action. Avoids adding `expo-calendar` and calendar permissions.
- Respect the existing offline queue (`src/queue`); visit creation can be online-only at first.

## Verification
- Backend tests `backend/tests/test_visits.py` (pattern of `test_day_lists.py`: owner/viewer/stranger roles, task pegging, 404 for non-members) and ICS tests: parse output with `icalendar`, check UID stability, UTC times, task checklist, token auth and rotation invalidating the old URL. Run `make test`, `ruff check`, `ruff format --check`, and the OpenAPI contract test.
- Web: Vitest tests for the dialog and calendar menu (Google URL building); `npm test`, `tsc --noEmit`.
- Mobile: jest tests for model helpers.
- Manual: download an `.ics` and open it in Apple Calendar; subscribe to the feed in Google and Fastmail; edit the visit and confirm the feed updates.
- E2E: add a Playwright case in `e2e/tests/` for creating a visit with tasks.

## Open risk
Google refreshes subscribed feeds slowly (hours); the UI will say so.
