# Allotment Planner: Implementation Plan

## Context
A multi-user app to map an allotment, plan and log work as tasks pinned to map features, print a daily todo list, upload progress photos with a historical timeline, post activity to a Mastodon account, and show a progress overview ("feel good" dashboard). A measuring checklist, filled in on site, corrects the drawn map to real-world dimensions.

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
| 8 Mastodon posting | AM-8 | Merged (in Review) |
| 9 Map from media (OpenSfM) | AM-9 | Merged (in Review) |
| 10 Polish: seed data, e2e, docs | AM-10 | Backlog |
| 11 Measuring checklist (map accuracy) | AM-17 | Backlog |
| CI: Gitea Actions | AM-11 | Merged (in Review) |

## Repo layout (monorepo)
```
backend/            Flask app (allotment/...), alembic migrations, tests, Dockerfile (dev + prod targets)
  allotment/{api,models,schemas,security,events,...}
frontend/           Vite + React + TS, generated API client, Dockerfile
worker/             Celery worker image (backend code + OpenSfM + GDAL)   (not yet created; AM-9)
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
`User`, `Allotment`, `Membership(user, allotment, role)` (done). Planned: `MapFeature` (allotment, kind: bed/path/shed/tree/etc., geometry incl. polygon/point/line, circle as point + `radius_m`, name, style jsonb), `MapLayer` (generated ortho: status, source job, bounds, tile URL), `Task` (title, description, status todo/doing/done, due date, priority, recurrence, assignee, optional `feature_id`, optional point geometry, completed_at/by), `Media` (kind photo/video, storage key, EXIF taken_at, lat/lng, heading, optional `feature_id`/`task_id`, caption), `MapJob` (input media, status, OpenSfM log, output layer), `ActivityLog` (event type, actor, subject refs, timestamp: feeds overview and Mastodon), `MastodonAccount` (instance URL, encrypted token, per-allotment, visibility), `Measurement` (allotment, kind edge|diagonal|radius|custom, endpoint A/B as feature + corner index, `value_m`, note, skipped, stale, measured_by/at) and `Allotment.length_unit` (`m`|`cm`|`ft_in`; values are always stored in metres).

### API (all under `/api/v1`)
Done: auth (register/login/refresh/me), allotments + members.
Planned: features (CRUD, GeoJSON in/out, bulk `PUT` of a FeatureCollection), tasks (CRUD, filter by date/feature/status, complete/uncomplete), media (presigned upload + register, list by feature/date), map-jobs (create from media ids, poll status), layers, timeline (media by date for compare), overview (per-day/week counts of tasks done, photos added, features changed + streak), printable todo (`GET /todo?date=` → HTML/PDF), Mastodon settings + test post, measurements (`GET` list with the drawn length of each item, `PATCH` value/note/skip, `POST` a custom corner-to-corner distance, `POST /sync` to generate or refresh the checklist, `POST /fit?preview=true|false` to preview or apply the corrected geometry).

### Key flows
- **Map from media**: user uploads photos/videos → Celery extracts EXIF GPS/heading/time (piexif/exifread; ffmpeg samples video frames, `ffprobe` location tags) → `MapJob` runs OpenSfM with GPS priors → GDAL (`gdalwarp`/`gdal2tiles`) orthoprojects to a georeferenced GeoTIFF + tiles → `MapLayer` shown as an overlay. Media without GPS can be placed manually by dragging on the map. The user then traces features over the layer (Geoman).
- **Daily todo**: print-optimised HTML (`@media print`) listing due/overdue tasks grouped by bed, with a small map snapshot; WeasyPrint as optional PDF endpoint.
- **Mastodon**: on task complete / photo upload / milestone, a Celery task posts a status (with media) using `Mastodon.py`; opt-in per event type, with a daily-digest option.
- **Progress overview**: aggregate `ActivityLog` by day/week; heatmap calendar, streak, "this week you completed N tasks", newest progress photos.
- **Measuring checklist** (phase 11): items are generated from the drawn features: a polygon with n corners gets its n edges plus a fan of n-3 diagonals from corner 1 (2n-3 distances fix a shape exactly), a line gets one item per segment, a circle one radius item. Sync is idempotent: unmeasured items whose corners vanished are deleted, measured ones are kept and flagged stale. **Fit**: project lon/lat to local metres about the allotment centroid, then Gauss-Newton least squares (numpy) per connected group of features, minimising `|p_i - p_j| - d` plus a weak prior toward the drawn positions, which pins translation, rotation and mirroring to what was drawn. The result reports residuals before and after, flags probable mismeasurements (residual over 0.15 m), says how many more measurements an under-determined shape needs, and goes through the existing feature validation (e.g. no self-intersection) before anything is written. Preview never writes; apply is one transaction.

## Frontend design
Vite + React + TS, React Router, TanStack Query, `openapi-typescript` + `openapi-fetch` generated client (`npm run gen:api`), Leaflet via `react-leaflet` + `@geoman-io/leaflet-geoman-free`. Pages: Login, Allotment switcher, **Map** (editor with feature list, task pins, overlay layers, media markers), **Tasks**, **Today** (printable), **Timeline** (photo history with date slider/compare), **Overview**, **Media upload**, **Settings** (members, Mastodon), **Measure** (phase 11). Tests: Vitest + Testing Library; Playwright e2e against the compose stack.

**Measure page** (mobile first, used on site): checklist grouped by feature with progress ("7 / 12 measured"); each row has a number input with a unit, notes and skip; a numbered-corner sketch (reusing `map/sketch.ts`) highlights the item being measured; "Apply to map" opens a preview of drawn against corrected shape with residuals, recheck warnings and what is still needed. A tolerant unit parser/formatter accepts `3.2`, `320cm`, `10ft 6in` and `10'6"`, shown per the allotment's `length_unit`. Phone fixes it needs: wrap the tab bar (a sixth tab overflows), `100dvh` for the shell, `inputmode="decimal"` on number fields, 44px touch targets.

## Observability and hooks (cross-cutting)
- **Domain event bus**: `emit(event_type, ...)` in `allotment/events.py`. Every state change goes through it. Subscribers: `ActivityLog` writer, Mastodon publisher, metrics counter, structured log line. New behaviour (webhooks, notifications) is added by registering a subscriber. Optional per-allotment outbound webhook subscriber. Measuring adds `measurement.recorded`, `measurement.synced` and `measurements.applied`; the last is recorded in `ActivityLog` and counts as a map edit on the overview.
- **Structured logging**: `structlog` JSON logs in api, worker and beat; `request_id` returned as `X-Request-ID` and propagated into Celery tasks.
- **Metrics**: `/metrics` (Prometheus): HTTP rate/latency by route, domain-event counts; planned Celery task counts/durations, map-job duration, Mastodon post success/failure, DB pool stats.
- **Tracing**: OpenTelemetry (Flask, SQLAlchemy, Celery, Redis, requests) via OTLP when `OTEL_EXPORTER_OTLP_ENDPOINT` is set; frontend will add `traceparent`.
- **Health**: `/healthz` (liveness), `/readyz` (DB, Redis) used by compose healthchecks.
- **Task visibility**: Celery events and Flower in the dev stack; map jobs and Mastodon posts persist status/error text and surface it in the UI.
- **Frontend**: error boundary and client error/web-vitals reporter to `POST /api/v1/telemetry/client`.
- **Dev observability stack** (compose profile `observability`): Prometheus, Grafana, Jaeger.
- **Tests**: events asserted per operation; smoke test for `/metrics`, `/healthz`, `/readyz` and request-ID propagation into a Celery task.

## Docker
`docker-compose.yml`: `db` (postgis), `redis`, `api`, `worker`, `beat`, `flower`, plus `prometheus`/`grafana`/`jaeger` under the `observability` profile. `.env.example`, `Makefile` (`up`, `down`, `test`, `observability`, `logs`). `frontend` and the shared `media` volume are in the stack. Planned: `flask seed-demo`, a compose test overlay. Risk: OpenSfM builds are slow; use a multi-stage worker Dockerfile with pinned versions, built separately so the rest of the stack starts quickly.

## Phases
1. **Scaffold & Docker**: repo, backend skeleton, event bus, logging, metrics, health, tracing, compose stack. ✅
2. **Auth, allotments, roles**: models, JWT, membership permissions, OpenAPI. ✅
3. **Map features CRUD**: PostGIS models + API; frontend map editor with Geoman draw/edit/delete. Adds the `frontend` image to CI and PostGIS to the CI test job. ✅
4. **Tasks**: CRUD, pin to feature, recurrence, Tasks page, map pins. ✅
5. **Today / print todo**: endpoint + print stylesheet. Done as a client-rendered sheet (SVG plot sketch with numbered pins) printed via the browser; a server-side PDF was dropped as unnecessary. ✅
6. **Media & timeline**: upload through the API (multipart) into pluggable storage, Celery task for EXIF/GPS/ffprobe metadata and thumbnails, signed short-lived file URLs with Range support for video, feature/task-linked photos, day-grouped timeline, before/after slider. ✅ Not yet: HEIC (rejected with a clear message), manual drag-to-place on the map.
7. **Progress overview**: an event-bus subscriber writes `ActivityLog` rows (task created/completed/reopened, media uploaded, feature changes); `GET /allotments/{id}/overview` aggregates per-day counts (UTC), this/last week, all-time totals, streaks (a day counts if a task was done, a photo added or the map edited; a streak ending yesterday is still alive), latest photos and completed tasks. Dashboard page: headline sentence, stat tiles, heatmap calendar, recent jobs and photos. Only events from now on are logged (no backfill). ✅
8. **Mastodon**: per-allotment account (instance + access token, token Fernet-encrypted and never returned, checked against the instance on save), opt-ins for finished jobs, photos and a daily digest, visibility (unlisted by default; nothing posts until switched on). Event-bus subscribers queue `MastodonPost` rows; the `allotment.send_mastodon_post` task claims a row atomically (no double posts), uploads photos as re-encoded 2560px JPEGs (EXIF and GPS never leave), sends with an `Idempotency-Key`, and on transient errors reschedules itself with backoff (30s, 2m, 8m, 32m; five attempts) while rejected tokens or content fail at once with the reason shown. A burst of photos is folded into one post of up to four pictures (per-allotment advisory lock, `MASTODON_PHOTO_BATCH_SECONDS`); beat runs the daily digest (`MASTODON_DIGEST_HOUR_UTC`, once per day per allotment, only if something happened) and a sweeper that re-queues lost posts. Instance URLs are user input, so https is required and loopback/private addresses and redirects are refused (`FEDIVERSE_ALLOW_PRIVATE_HOSTS=1` for local testing). Settings page: connect/disconnect, test post (sent as `direct`, visible only to the account), post history with status and Retry. Videos are not posted. ✅
   Connecting: in Mastodon, Preferences → Development → New application with scopes `read:accounts`, `write:statuses`, `write:media`; paste the access token into Settings.
9. **Map from media (OpenSfM + GDAL)**: `MapJob` and `MapLayer` models; `POST /map-jobs` takes 5+ overlapping photos (3+ with a location; videos are sampled at 1 frame/s) and queues `allotment.run_map_job` on a dedicated `mapping` queue, served by the separate `mapper` container (`make mapper`; compose profile `mapping`) so thumbnails and Mastodon posts are never stuck behind it. The worker image (`worker/Dockerfile`, Ubuntu 24.04) compiles OpenSfM from a pinned commit into its own virtualenv and runs it as a subprocess; the app only reads its JSON. Pipeline: dataset prep (EXIF/DB locations written as `exif_overrides`, all at the stated camera height because phone altitude is unreliable) -> `extract_metadata, detect_features, match_features, create_tracks, reconstruct, undistort` -> ground plane fitted to the sparse points (plants poking up are rejected) -> every photo's pixels cast onto that plane to give GCPs (`mapping_geo.py`, plain numpy and unit-tested) -> GDAL: `gdal_translate -gcp` per photo, one `gdalwarp -tps` mosaic (nearest photos drawn last), `gdal2tiles --xyz`. Tiles live in storage under `allotments/{id}/layers/{layer}/tiles/z/x/y.png` and are served through signed, expiring links (an `<img>` can't send a bearer token); a missing tile returns a blank PNG. The job log tail, stage, cancel (queued at once, running within ~10 s) and failure reasons are persisted and shown in the UI. Layers page: list, show/hide, opacity, delete; build form with the same readiness rules as the server; recent builds with progress. Visible layers are drawn on the map under the shapes. `layer.created` counts as a map edit on the overview. The worker image is built and pushed by the `build` workflow (`allotment-worker`).
   **Accuracy and limits.** The model is a flat ground plane (a fitted, possibly tilted plane), so hills, tall objects and very oblique shots distort; ground further than 12 camera heights away is ignored. Position and, importantly, **scale come from the photos' GPS**: phone jitter of 1-3 m across a plot shows up as a scale error of about 1-4% (checked: 0.3 m noise gives ~1%, 1.5 m noise gives ~4%, with position within 0.5 m either way). The map is shape-consistent but should be corrected with a measured distance; that is what the measuring checklist (phase 11) and ticket AM-18 are for. `make mapping-check` renders a textured ground plane from 25 GPS-tagged overhead cameras, runs it through the real pipeline and compares the tiles with the known texture (scale and rotation scans, offset, correlation). It is not in CI because it needs the 3.5 GB worker image. Real hand-held photos have only been checked through this synthetic scene.
10. **Polish**: seed data, e2e tests, README/docs.
11. **Measuring checklist** (AM-17): `Measurement` model + `length_unit`, checklist generation from features, least-squares fit with preview/apply, Measure page with units and corner sketch, phone layout fixes. Depends only on map features (AM-3), so it can start at any point. Not in scope: corner numbers drawn on the Leaflet map, a printable paper checklist, GPS-assisted measuring, anchoring scale/rotation to surveyed points.

## Verification
- Backend: `pytest` (API tests; Celery eager; Mastodon mocked; OpenSfM pipeline on a small sample set marked slow); PostGIS-backed tests once geometry models land.
- Frontend: `vitest`, `tsc --noEmit`; Playwright e2e: register → create allotment → draw bed → add task pinned to bed → complete it → upload photo → see it in timeline and overview → print todo renders.
- `docker compose up --build` from a clean checkout reaches healthy; `http://localhost:8000/api/docs` and `http://localhost:5173` load; `flask seed-demo` populates a demo.
- OpenAPI: generated TS client regenerates with no diff in CI.
- Measuring: solver unit tests (a skewed rectangle fits exactly to 10 x 5 from edges plus one diagonal; a trapezoid; one bad measurement is flagged `recheck` with small residuals elsewhere; an under-determined shape reports its missing constraints; no mirror flip; circle radius), sync idempotence and stale handling, role tests (viewer 403 on writes, non-member 404, preview writes nothing, an invalid fit returns 422 and changes nothing), unit-parser tests, and an e2e step: draw a slightly wrong bed, measure, preview, apply, check its size on the map.
