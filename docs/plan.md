# Allotment Planner: Implementation Plan

## Context
A multi-user app to map an allotment, plan and log work as tasks pinned to map features, print a daily todo list, upload progress photos with a historical timeline, post activity to a Mastodon account, and show a progress overview ("feel good" dashboard).

Decisions: Leaflet + Geoman map editor; OpenSfM + GDAL for photo/video → orthomap; ActivityPub via posting to an existing Mastodon account through its API; multi-user with roles. Stack: Flask / Celery / Postgres (PostGIS) with OpenAPI; TypeScript + React frontend. Docker compose for test instances; Gitea Actions for CI (see [ci.md](ci.md)).

Tickets live in YouTrack project **AM** (Allotment Manager) at pm.daubney.dev. Workflow: one feature branch per ticket (`AM-<n>-short-name`), small regular commits, merge to `main` when tests pass.

## Status
| Phase | Ticket | State |
|---|---|---|
| 1 Scaffold, Docker, observability | AM-1 | Merged |
| 2 Auth, allotments, roles | AM-2 | Merged (in Review) |
| 3 Map features CRUD + editor | AM-3 | Merged (in Review) |
| 4 Tasks pinned to features | AM-4 | Merged (in Review) |
| 5 Printable daily todo | AM-5 | Merged (in Review) |
| 6 Media upload, EXIF, timeline | AM-6 | Merged (in Review) |
| 7 Progress overview | AM-7 | Merged (in Review) |
| 8 Mastodon posting | AM-8 | Backlog |
| 9 Map from media (OpenSfM) | AM-9 | Backlog |
| 10 Polish: seed data, e2e, docs | AM-10 | Backlog |
| CI: Gitea Actions | AM-11 | Merged (in Review) |

## Repo layout (monorepo)
```
backend/            Flask app (allotment/...), alembic migrations, tests, Dockerfile (dev + prod targets)
  allotment/{api,models,schemas,security,events,...}
frontend/           Vite + React + TS, generated API client, Dockerfile   (not yet created)
worker/             Celery worker image (backend code + OpenSfM + GDAL)   (not yet created)
.gitea/workflows/   test.yml, build.yml
docker-compose.yml  dev stack, with an `observability` profile
docs/ , .env.example, Makefile
```

## Backend design
- **Flask + flask-smorest** (marshmallow schemas → OpenAPI 3 at `/api/openapi.json`, Swagger UI at `/api/docs`). Source of truth for the frontend client.
- **SQLAlchemy 2 + Alembic**, Postgres with **PostGIS** (`postgis/postgis`); geometries as `geometry(…, 4326)` via GeoAlchemy2. Leaflet works in lat/lng, so no local-canvas coordinates. Alembic autogenerate ignores tables we don't own (`include_object` in `extensions.py`).
- **Celery + Redis**: media processing (EXIF, thumbnails), photogrammetry, Mastodon posting, daily rollups.
- **Auth**: Flask-JWT-Extended, argon2 hashes. Roles per allotment through memberships: `owner`, `editor`, `viewer`.
- **Storage**: `allotment/storage.py` with two backends behind one interface: plain files on a shared Docker volume (default; used by compose and tests) or any S3-compatible service (`STORAGE_BACKEND=s3`, tested against moto). MinIO was dropped: its container images are no longer published. Orthomaps will be stored as COG GeoTIFF + XYZ tiles.

### Data model
`User`, `Allotment`, `Membership(user, allotment, role)` (done). Planned: `MapFeature` (allotment, kind: bed/path/shed/tree/etc., geometry incl. polygon/point/line, circle as point + `radius_m`, name, style jsonb), `MapLayer` (generated ortho: status, source job, bounds, tile URL), `Task` (title, description, status todo/doing/done, due date, priority, recurrence, assignee, optional `feature_id`, optional point geometry, completed_at/by), `Media` (kind photo/video, storage key, EXIF taken_at, lat/lng, heading, optional `feature_id`/`task_id`, caption), `MapJob` (input media, status, OpenSfM log, output layer), `ActivityLog` (event type, actor, subject refs, timestamp: feeds overview and Mastodon), `MastodonAccount` (instance URL, encrypted token, per-allotment, visibility).

### API (all under `/api/v1`)
Done: auth (register/login/refresh/me), allotments + members.
Planned: features (CRUD, GeoJSON in/out, bulk `PUT` of a FeatureCollection), tasks (CRUD, filter by date/feature/status, complete/uncomplete), media (presigned upload + register, list by feature/date), map-jobs (create from media ids, poll status), layers, timeline (media by date for compare), overview (per-day/week counts of tasks done, photos added, features changed + streak), printable todo (`GET /todo?date=` → HTML/PDF), Mastodon settings + test post.

### Key flows
- **Map from media**: user uploads photos/videos → Celery extracts EXIF GPS/heading/time (piexif/exifread; ffmpeg samples video frames, `ffprobe` location tags) → `MapJob` runs OpenSfM with GPS priors → GDAL (`gdalwarp`/`gdal2tiles`) orthoprojects to a georeferenced GeoTIFF + tiles → `MapLayer` shown as an overlay. Media without GPS can be placed manually by dragging on the map. The user then traces features over the layer (Geoman).
- **Daily todo**: print-optimised HTML (`@media print`) listing due/overdue tasks grouped by bed, with a small map snapshot; WeasyPrint as optional PDF endpoint.
- **Mastodon**: on task complete / photo upload / milestone, a Celery task posts a status (with media) using `Mastodon.py`; opt-in per event type, with a daily-digest option.
- **Progress overview**: aggregate `ActivityLog` by day/week; heatmap calendar, streak, "this week you completed N tasks", newest progress photos.

## Frontend design
Vite + React + TS, React Router, TanStack Query, `openapi-typescript` + `openapi-fetch` generated client (`npm run gen:api`), Leaflet via `react-leaflet` + `@geoman-io/leaflet-geoman-free`. Pages: Login, Allotment switcher, **Map** (editor with feature list, task pins, overlay layers, media markers), **Tasks**, **Today** (printable), **Timeline** (photo history with date slider/compare), **Overview**, **Media upload**, **Settings** (members, Mastodon). Tests: Vitest + Testing Library; Playwright e2e against the compose stack.

## Observability and hooks (cross-cutting)
- **Domain event bus**: `emit(event_type, ...)` in `allotment/events.py`. Every state change goes through it. Subscribers: `ActivityLog` writer, Mastodon publisher, metrics counter, structured log line. New behaviour (webhooks, notifications) is added by registering a subscriber. Optional per-allotment outbound webhook subscriber.
- **Structured logging**: `structlog` JSON logs in api, worker and beat; `request_id` returned as `X-Request-ID` and propagated into Celery tasks.
- **Metrics**: `/metrics` (Prometheus): HTTP rate/latency by route, domain-event counts; planned Celery task counts/durations, map-job duration, Mastodon post success/failure, DB pool stats.
- **Tracing**: OpenTelemetry (Flask, SQLAlchemy, Celery, Redis, requests) via OTLP when `OTEL_EXPORTER_OTLP_ENDPOINT` is set; frontend will add `traceparent`.
- **Health**: `/healthz` (liveness), `/readyz` (DB, Redis) used by compose healthchecks.
- **Task visibility**: Celery events and Flower in the dev stack; map jobs and Mastodon posts persist status/error text and surface it in the UI.
- **Frontend**: error boundary and client error/web-vitals reporter to `POST /api/v1/telemetry/client`.
- **Dev observability stack** (compose profile `observability`): Prometheus, Grafana, Jaeger.
- **Tests**: events asserted per operation; smoke test for `/metrics`, `/healthz`, `/readyz` and request-ID propagation into a Celery task.

## Docker
`docker-compose.yml`: `db` (postgis), `redis`, `api`, `worker`, `beat`, `flower`, plus `prometheus`/`grafana`/`jaeger` under the `observability` profile. `.env.example`, `Makefile` (`up`, `down`, `test`, `observability`, `logs`). Planned: `frontend` service, `flask seed-demo`, a compose test overlay. Risk: OpenSfM builds are slow; use a multi-stage worker Dockerfile with pinned versions, built separately so the rest of the stack starts quickly.

## Phases
1. **Scaffold & Docker**: repo, backend skeleton, event bus, logging, metrics, health, tracing, compose stack. ✅
2. **Auth, allotments, roles**: models, JWT, membership permissions, OpenAPI. ✅
3. **Map features CRUD**: PostGIS models + API; frontend map editor with Geoman draw/edit/delete. Adds the `frontend` image to CI and PostGIS to the CI test job. ✅
4. **Tasks**: CRUD, pin to feature, recurrence, Tasks page, map pins. ✅
5. **Today / print todo**: endpoint + print stylesheet. Done as a client-rendered sheet (SVG plot sketch with numbered pins) printed via the browser; a server-side PDF was dropped as unnecessary. ✅
6. **Media & timeline**: upload through the API (multipart) into pluggable storage, Celery task for EXIF/GPS/ffprobe metadata and thumbnails, signed short-lived file URLs with Range support for video, feature/task-linked photos, day-grouped timeline, before/after slider. ✅ Not yet: HEIC (rejected with a clear message), manual drag-to-place on the map.
7. **Progress overview**: an event-bus subscriber writes `ActivityLog` rows (task created/completed/reopened, media uploaded, feature changes); `GET /allotments/{id}/overview` aggregates per-day counts (UTC), this/last week, all-time totals, streaks (a day counts if a task was done, a photo added or the map edited; a streak ending yesterday is still alive), latest photos and completed tasks. Dashboard page: headline sentence, stat tiles, heatmap calendar, recent jobs and photos. Only events from now on are logged (no backfill). ✅
8. **Mastodon**: settings, posting task, event opt-ins, digest.
9. **Map from media (OpenSfM)**: worker image, `MapJob` pipeline, ortho overlay, manual placement fallback. Adds the `worker` image to CI.
10. **Polish**: seed data, e2e tests, README/docs.

## Verification
- Backend: `pytest` (API tests; Celery eager; Mastodon mocked; OpenSfM pipeline on a small sample set marked slow); PostGIS-backed tests once geometry models land.
- Frontend: `vitest`, `tsc --noEmit`; Playwright e2e: register → create allotment → draw bed → add task pinned to bed → complete it → upload photo → see it in timeline and overview → print todo renders.
- `docker compose up --build` from a clean checkout reaches healthy; `http://localhost:8000/api/docs` and `http://localhost:5173` load; `flask seed-demo` populates a demo.
- OpenAPI: generated TS client regenerates with no diff in CI.
