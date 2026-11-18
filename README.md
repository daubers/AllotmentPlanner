<p align="center"><img src="docs/brand/logo.svg" width="96" alt="Allotment Planner logo: a map pin with a seedling"></p>

# Allotment Planner

Plan and log the work on an allotment: draw the plot on a map, pin tasks to beds, print the day's list, keep a photo history, post progress to Mastodon, and get a "look what we did" overview. A phone app records photos with their GPS and compass, helps build a map from them, and corrects the drawn plot to real sizes from tape-measure readings.

- **Web app** (React + TypeScript): map editor (Leaflet), tasks, printable daily list, photo timeline with before/after slider, progress overview, Mastodon settings, map layers.
- **API** (Flask, PostgreSQL + PostGIS, Celery, Redis): multi-user with owner / editor / viewer roles, OpenAPI at `/api/docs`.
- **Mapper** (optional, heavy): builds a map from photos and video with OpenSfM and GDAL, recognises objects (water butts, trees, sheds) with local models, and uses a GoPro's GPS track when there is one.
- **Phone app** (Expo / React Native, Android and iOS): sign in, guided photo capture, measuring checklist, offline queue.

A public landing page, a [privacy page](frontend/src/public/Privacy.tsx) (`/privacy`) and user help (`/help`) are part of the web app and work without signing in; the screenshots are described in [docs/screenshots.md](docs/screenshots.md). Set the contact address and date for the privacy page in `frontend/src/public/site.ts`.

Planned work, with the reasoning behind each piece, is in [docs/plan.md](docs/plan.md); tickets live in YouTrack project **AM**.

> **Status.** The server and web app are used and tested. The phone app has tests, a clean bundle and screenshot review, but had not yet been run on a real device when this was written. Building the plot outline automatically from photos works on synthetic data but did not on the first real photo set; the measuring checklist is the dependable route to real dimensions. See [docs/plan.md](docs/plan.md) for the honest details.

## How it fits together

```
 phone app ─┐                       ┌─ worker  (thumbnails, metadata, Mastodon posts)
            ├─ HTTPS ─ nginx ─ api ─┼─ beat    (schedules: daily digest, sweeper)
 web app ───┘  (frontend)    Flask  ├─ mapper  (OpenSfM + GDAL + recognition models; optional)
                                │   └─ redis   (Celery broker)
                                ├─ PostgreSQL + PostGIS
                                └─ media storage (a volume, or S3-compatible)
```

```
backend/      Flask app (allotment/…), Alembic migrations, tests, Dockerfile (dev and prod targets)
frontend/     Vite + React + TypeScript, generated API client, Dockerfile (dev and nginx prod targets)
mobile/       Expo app (Android and iOS)
worker/       Dockerfile for the mapper image (OpenSfM, GDAL, torch)
deploy/       Production compose file, its settings template, Prometheus config
e2e/          Playwright browser tests
scripts/      mapping_check.py: end-to-end check of the mapping pipeline on a synthetic scene
docs/         plan.md (design and phases), ci.md (CI and images), mobile.md (phone app)
```

## Quick start (development)

You need Docker with Compose v2. Everything runs in containers.

```
git clone ssh://git@git.daubney.dev:222/matt/Allotment-Manager.git
cd Allotment-Manager
make up          # copies .env.example to .env, builds, starts everything, migrates the database
```

Then open:

| What | Address |
|---|---|
| Web app (Vite dev server, hot reload) | http://localhost:5173 |
| API and interactive docs | http://localhost:8000/api/docs |
| Celery monitor (Flower) | http://localhost:5555 |

Register an account in the web app, create an allotment, and start drawing. `make down` stops everything; your data stays in Docker volumes (`pgdata`, `media`).

Optional extras:

```
make mapper          # the photo-mapping worker (a large image; the first build takes a while)
make observability   # Prometheus (9090), Grafana (3000), Jaeger (16686)
make logs            # follow api and worker logs
```

The database schema is brought up to date by a one-shot `migrate` service on every `make up`. `make migrate` runs it by hand.

## Development

```
make test                                  # backend tests, in a container
ruff check backend && ruff format backend  # lint and format (CI checks both)

cd frontend && npm ci
npm run typecheck && npm test              # TypeScript and Vitest
npm run gen:api                            # regenerate the API client after the API changes

cd mobile && npm ci
npm run typecheck && npm test              # TypeScript and Jest

make e2e                                   # Playwright browser tests against the running stack
make mapping-check                         # synthetic end-to-end check of the mapper (needs `make mapper`)
```

**Changing the API.** The OpenAPI document drives the TypeScript client. After changing endpoints or schemas: write the document with `docker compose run --rm --no-deps -v "$PWD/frontend:/out" api flask openapi write /out/openapi.json`, run `npm run gen:api` in `frontend/`, then `npm run gen:api` in `mobile/` (it copies the web app's generated types). CI fails if either is out of date.

**Changing the database.** Add an Alembic migration under `backend/migrations/versions/` (`docker compose run --rm api flask db migrate -m "what changed"`, then read and edit what it wrote) and run `make migrate`.

**Backend tests in a container** use the image's copy of `tests/`; when you add or change tests, mount them: `docker compose run --rm --no-deps -v "$PWD/backend/tests:/app/tests" api pytest -q`.

**Working method.** One feature branch per ticket (`AM-<n>-short-name`), small regular commits, merge to `main` only when the tests pass and CI is green. See [docs/ci.md](docs/ci.md).

## Build

CI is Gitea Actions ([docs/ci.md](docs/ci.md)):

| Workflow | When | What |
|---|---|---|
| `test.yml` | every push and PR | ruff, backend tests with a PostGIS service, frontend typecheck/tests/build, phone app typecheck/tests/bundle, generated API types up to date, compose files valid |
| `build.yml` | push to `main`, tags `v*` | repeats the backend tests, then builds and pushes three images |

Images are pushed to the `allotment` Docker feed on ProGet as `pkgs.daubney.dev/allotment/…`:

| Image | Contents |
|---|---|
| `allotment-api` | the Flask app (gunicorn); also run as the Celery worker and beat |
| `allotment-frontend` | the built web app served by nginx, which proxies `/api` to the `api` service |
| `allotment-worker` | the mapper: OpenSfM compiled from source, GDAL, torch (CPU) and the recognition code |

Tags: `latest` (main), `sha-<commit>`, the branch name, and `X.Y.Z` / `X.Y` for releases. The recognition models (about 1.3 GB) are **not** in the image; they download into a volume the first time a map job needs them. CI needs one secret, `PKGS_API_KEY` (the ProGet API key; the login user is `api`).

**Release:** `git tag v0.2.0 && git push origin v0.2.0`.

**Build the images yourself:**

```
docker build --target prod -t allotment-api backend
docker build --target prod -t allotment-frontend frontend
docker build -f worker/Dockerfile -t allotment-worker backend    # slow: compiles OpenSfM, about 5 minutes
```

## Deployment

The supported way to run it is the production compose file, [`deploy/docker-compose.prod.yml`](deploy/docker-compose.prod.yml), which runs the published images. It was tested from a clean start (migration, health, web app, API through nginx, and a photo upload processed by the worker). The optional mapper service was validated but not run. It needs a Linux host with Docker and Compose v2, a few GB of RAM (the mapper needs considerably more: building its image alone takes about 4 GB), and disk for your photos.

### 1. Get the files onto the server

You only need the `deploy/` folder. Either clone the repository or copy these two files:

```
mkdir allotment && cd allotment
# copy deploy/docker-compose.prod.yml here as docker-compose.yml, and:
cp .env.production.example .env
```

### 2. Settings

Edit `.env`. The ones that matter:

| Setting | What to put |
|---|---|
| `POSTGRES_PASSWORD` | a long random password (`openssl rand -hex 32`) |
| `JWT_SECRET_KEY` | a different long random value; signs logins. Compose refuses to start without it |
| `TOKEN_ENCRYPTION_KEY` | another random value; encrypts stored Mastodon tokens. **Keep it safe**: losing it means reconnecting Mastodon |
| `REGISTRY`, `TAG` | where the images are (`pkgs.daubney.dev/allotment`) and which version (`latest`, `0.2.0`, or `sha-…` to pin) |
| `REGISTRATION` | `invite` (the default in the production file) or `open`; see [Who can sign up](#5-who-can-sign-up) |
| `HTTP_PORT` | the one port the web app and API are served on (default 8080) |

The full list, including S3 storage and mapping limits, is in the file and in [Configuration](#configuration).

### 3. Start it

```
docker login pkgs.daubney.dev -u api   # the ProGet API key as the password
docker compose up -d
docker compose ps                     # everything Up (healthy); `migrate` and `volumes-init` show Exited (0)
```

Open `http://<server>:8080`, register the first account, create your allotment. On start-up a `volumes-init` step makes the data volumes writable and a `migrate` step upgrades the database; the apps wait for both.

To also run the photo-mapping worker: `docker compose --profile mapping up -d` (the first map build downloads about 1.3 GB of models).

To read seed packets from photos (**Seeds → Scan packets**), also run the packet reader: `docker compose --profile vision up -d`. It needs no GPU and no model download (a CPU OCR engine ships in the image); a packet takes about 20 seconds. It is a separate worker so a scan never waits behind a map build, and it can run on another machine like any other worker (`WORKER_QUEUES=vision`).

### 4. Put TLS in front of it

Serve it over HTTPS before exposing it to the internet; the phone app also needs HTTPS for anything outside your home network. The compose file publishes only `HTTP_PORT`, so point a reverse proxy at it. With Caddy, which gets certificates by itself (`Caddyfile`):

```
plot.example.com {
    reverse_proxy localhost:8080
}
```

With nginx, add TLS as usual and allow large uploads (a GoPro chapter is about 4 GB):

```
client_max_body_size 4g;
proxy_request_buffering off;
proxy_read_timeout 3600s;
proxy_send_timeout 3600s;
```

(These two snippets are standard configuration but were not run as part of testing.)

### 5. Who can sign up

The production compose file starts with `REGISTRATION=invite`, so the server is closed to strangers. The very first account can be created on an empty server (do this straight after the first start, before the server is reachable by anyone else), and from then on `POST /auth/register` is refused unless the request carries an invite code.

To bring someone in, an allotment owner opens **Settings → Invite someone**, enters the person's email and a role, and sends them the link it makes. The link opens the registration form with the code and email filled in; they choose a name and password and are added to that allotment. Details worth knowing:

- An invite is tied to one email address and expires after `INVITE_TTL_DAYS` (7). It cannot be used for another address, and once that address has an account it is spent. It is a signed code, not a database row, so it cannot be revoked individually; rotating `JWT_SECRET_KEY` cancels every outstanding invite (and signs everyone out).
- People who already have an account are added with the members API instead (`POST /api/v1/allotments/{id}/members`).
- With `REGISTRATION=open` anyone who can reach the server can still create an empty account, though they see nothing of other people's allotments. Use that only on a private network.
- **Single sign-on** (OpenID Connect) can sit beside passwords: set `OIDC_PROVIDERS` and `PUBLIC_URL`, see [docs/oidc.md](docs/oidc.md). It follows the same rule: a provider sign-in only works for someone who already has an account or holds an invite.

### 6. Workers on other machines

Only the API, web app, database, Redis and the scheduler (`beat`, which must run exactly once) have to live together on the main server. Every **Celery worker can run on any machine on your network**, with or without a GPU: the general worker (thumbnails, Mastodon posts), the mapping worker (photo mapping and object recognition) and, later, the packet reader. The map job is the heavy one; OpenSfM is CPU only, so a second machine's cores and RAM matter as much as any graphics card, and recognition (Grounding DINO and SAM) is about ten times faster on a GPU than on the same machine's CPU.

Nothing is shared as a volume: photos and map tiles go through S3 (SeaweedFS), and a worker talks to Redis and Postgres over the LAN. That is a rule for all new code too (the tests enforce it): workers reach files only through the storage layer, never a path on disk, except their own scratch space. **Keep these ports off the internet**: they are for your home network only, and your server's firewall should allow them from the workers' addresses alone.

**Main server**

1. Give it a fixed LAN address. In `.env` set `LAN_IP`, `REDIS_PASSWORD`, `REDIS_URL=redis://:<REDIS_PASSWORD>@redis:6379/0`, `STORAGE_BACKEND=s3`, `S3_ENDPOINT_URL=http://s3:9000`, `S3_BUCKET`, `S3_ACCESS_KEY` and `S3_SECRET_KEY` (the last two become the S3 service's login; 8 or more characters). The commented block at the end of `.env.production.example` lists them.
2. Start with the LAN add-on: `docker compose -f docker-compose.prod.yml -f docker-compose.lan.yml up -d`. It publishes Redis (password protected), Postgres and the S3 service on `LAN_IP` only.
3. If you already have photos, copy them from the `media` volume into the bucket once: `docker compose run --rm api flask copy-media-to-s3` (add `--dry-run` to see what it would do). It leaves the files where they are and can be repeated.
4. A queue can be served from several machines to share the load, but stop serving it here when you move it: do not leave `--profile mapping` (or `--profile vision`) running on the main server by accident.

**Worker machine** (Docker installed, the repository checked out)

| Card | On the host | `TORCH_INDEX` | Compose add-on |
|---|---|---|---|
| none (CPU only) | nothing | `cpu` | none |
| NVIDIA | the NVIDIA driver and the NVIDIA Container Toolkit (`nvidia-ctk runtime configure --runtime=docker`, then restart Docker). `docker run --rm --gpus all ubuntu nvidia-smi` must list the card | `cu126` | `docker-compose.remote-worker.nvidia.yml` |
| AMD (RX 6000 series and similar) | the normal `amdgpu` kernel driver; `/dev/kfd` and `/dev/dri` must exist. Nothing else: ROCm's libraries come inside the image | `rocm7.1` | `docker-compose.remote-worker.amd.yml` |

```sh
cd deploy
cp .env.remote-worker.example .env.remote-worker   # MAIN_SERVER, the same secrets as the main server, WORKER_QUEUES, TORCH_INDEX
./build-remote-worker.sh                           # builds the image on this machine
docker compose --env-file .env.remote-worker -f docker-compose.remote-worker.yml up -d                                      # CPU only
docker compose --env-file .env.remote-worker -f docker-compose.remote-worker.yml -f docker-compose.remote-worker.amd.yml up -d  # or with a GPU
docker compose --env-file .env.remote-worker -f docker-compose.remote-worker.yml logs -f worker
```

`WORKER_QUEUES` (default `mapping`; `vision` reads seed packets, and `mapping,vision` does both) says which queues this machine serves and `WORKER_CONCURRENCY` (default 1) how many jobs at once; a map job can use several GB of RAM. The general worker (queue `celery`) needs none of OpenSfM or PyTorch: to run it elsewhere use the published API image with the same environment and `celery -A allotment.celery_app:celery worker`.

The first build takes a while (OpenSfM is compiled; the GPU builds of PyTorch alone are 3 to 6 GB and the finished AMD image is about 20 GB), and the image is built here instead of pulled because a registry will not take layers that large. The recognition models (about 1.3 GB) download on the first job. With a GPU, the log line `detector_loading ... device=cuda gpu=...` shows the card in use; once it works, set `TORCH_DEVICE=cuda` so a broken GPU setup fails loudly instead of quietly running on the CPU.

*AMD notes.* RX 6600/6700 cards (gfx1031/1032) are not on ROCm's supported list; the add-on sets `HSA_OVERRIDE_GFX_VERSION=10.3.0` so they run as the supported gfx1030. Without it the worker crashes on its first GPU call. Set `RENDER_GID` to your host's `render` group id (`getent group render`). Cards with 8 GB of memory are enough for the recognition models.

### Deleting accounts and data exports
People delete their own account, and download a copy of their data, from **Your account** in the web app or **Account** in the phone app (`DELETE /api/v1/auth/me`, `POST /api/v1/auth/me/export`). You do not need to do anything by hand.
- **Deleting** removes the account and any allotment only that person belongs to, with its photos and other files. It is refused while they are the only owner of an allotment other people belong to; they hand it over first. What they added to shared allotments stays, no longer linked to them. A person with no password confirms with their single sign-on provider.
- **Exports** are built by the Celery worker, so the `worker` service must be running or a request stays "preparing". The zip is stored in the media storage under `exports/<user id>/` and deleted by a daily scheduled job (`allotment.prune_account_exports`, which needs the `beat` service) after `ACCOUNT_EXPORT_TTL_HOURS` (48).
- There is no admin tool for deleting or exporting someone else's account. The privacy page tells people who cannot sign in to email you (`CONTACT_EMAIL` in `frontend/src/public/site.ts`).

### Backups

Two things hold your data: the database and the photo volume. Back up both, and `.env`.

```
docker compose exec -T db pg_dump -U allotment allotment | gzip > allotment-$(date +%F).sql.gz
docker run --rm -v allotment_media:/data -v "$PWD":/backup busybox \
    tar czf /backup/media-$(date +%F).tgz -C /data .
```

To restore into a fresh install: start only the database (`docker compose up -d db`), load the dump (`gunzip -c allotment-….sql.gz | docker compose exec -T db psql -U allotment allotment`), unpack the media archive into the `allotment_media` volume the same way as above (with `tar xzf`), then `docker compose up -d`. (Volume names start with the compose project name, `allotment`. These commands were written from the compose file, not rehearsed on a real backup; try a restore on a spare machine before you rely on them.)

### Upgrading

```
docker compose pull
docker compose up -d        # the migrate step upgrades the database first
```

To pin a known-good version, set `TAG` in `.env`. Rolling back the *code* is `TAG=<previous>` and `up -d`, but migrations only go forward: if a release changed the database, restore the backup you took first, or run `docker compose run --rm migrate flask db downgrade -1` for a single step.

### Health and monitoring

- `GET /healthz` (process is up) and `GET /readyz` (database and Redis reachable) on the API; the compose healthcheck uses `/readyz`.
- `GET /metrics` is Prometheus format (request counts and latencies, domain events, Celery task outcomes). It is served by the API but not through the public port, so scrape it from inside the Docker network (`api:8000`); `deploy/prometheus/prometheus.yml` shows a scrape config.
- Logs are structured JSON on stdout: `docker compose logs -f api worker`.
- **Admin page** (`/admin`, linked in the top bar for admins): which Celery workers are online (queues, what each is running, uptime, version, GPU), queue lengths, the schedule and when each scheduled job last ran, recent map jobs / packet scans / Mastodon posts, database, Redis and storage checks, and a searchable log. The log keeps warnings, errors and task outcomes from the API and every worker (including ones on other machines) in the database for `LOG_RETENTION_DAYS` days. Give someone access with `docker compose exec api flask make-admin you@example.com` (add `--revoke` to take it away).
- OpenTelemetry traces are exported if `OTEL_EXPORTER_OTLP_ENDPOINT` is set.

### Troubleshooting

| Symptom | Likely cause |
|---|---|
| `docker compose up` stops with "set POSTGRES_PASSWORD…" | a required setting is missing from `.env` |
| `pull access denied` | `docker login pkgs.daubney.dev -u api` with the ProGet API key, and check `REGISTRY` |
| Uploads stay "pending" | the `worker` container is down: `docker compose logs worker` |
| Map builds stay "queued" | the mapper isn't running: start it with `--profile mapping` |
| Packet photos stay "waiting its turn" | the packet reader isn't running: start it with `--profile vision` |
| Big uploads fail through your proxy | raise its body-size limit and timeouts (see TLS above) |
| The phone app can't connect | use the address the *phone* can reach (not `localhost`), with `https://` if it is on the internet |

## Phone app

The app is in [`mobile/`](mobile/); details are in [docs/mobile.md](docs/mobile.md).

```
cd mobile && npm ci
npx expo start        # scan the QR code with Expo Go (enough for sign-in and the screens)
```

The camera, GPS, compass and background uploads need a **development build**:

```
npx expo prebuild                 # writes ios/ and android/ (not committed)
npx expo run:android              # or run:ios (macOS with Xcode)
```

On the sign-in screen enter the address of your server: `http://<computer's LAN IP>:8000` for the development stack, or your deployment's address (`https://plot.example.com`). `localhost` means the phone itself.

To build the app for phones, see [docs/mobile.md](docs/mobile.md#building-the-app-which-route-to-use). In short, there are two routes and CI uses only the first:
- **Android APK with Gradle** (`mobile/scripts/build-android.sh`, run by CI on a `v*` tag): no Expo account needed, for installing on your own phones.
- **EAS Build** (Expo's cloud service, **started by hand**): the only way to build iOS without a Mac, and what goes to the App Store and Google Play. From `mobile/`: `envbao exec -q expo -- npx eas-cli build --platform android --profile preview` (the Expo token comes from OpenBao; profiles are in `mobile/eas.json`). The first build on each platform needs credentials set up interactively; iOS needs an Apple developer account. Plain HTTP to a LAN address works in the `development` and `preview` builds and the CI APK, not in `production`: see [docs/store-review.md](docs/store-review.md).

To look at the screens without a phone: `EXPO_PUBLIC_DEMO=1 npx expo start --web` serves them in a browser with built-in fake data.

## Configuration

Set in `.env` (development: `.env.example`; production: `deploy/.env.production.example`).

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | compose default | SQLAlchemy URL of the PostGIS database |
| `REDIS_URL` | `redis://redis:6379/0` | Celery broker |
| `JWT_SECRET_KEY` | insecure dev value | signs logins; **must** be set in production |
| `TOKEN_ENCRYPTION_KEY` | derived from the JWT key | encrypts stored Mastodon tokens |
| `STORAGE_BACKEND` | `file` | `file` (a volume) or `s3` |
| `MEDIA_ROOT` | `/data/media` | where the `file` backend stores photos |
| `S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` | | for `s3` |
| `REGISTRATION` | `open` (the production compose file sets `invite`) | `open`: anyone can register. `invite`: only the first account on an empty server, then people an owner has invited |
| `INVITE_TTL_DAYS` | `7` | how long an invite link stays valid |
| `TORCH_DEVICE` | `auto` | worker only: `auto` uses a GPU if there is one, `cpu` never does, `cuda` insists (and refuses to start without one) |
| `MAX_UPLOAD_MB` | `4096` | largest accepted upload; keep nginx's `client_max_body_size` in step |
| `LOG_LEVEL` | `INFO` | |
| `LOG_TO_DB` / `LOG_RETENTION_DAYS` | `1` / `14` | keep warnings, errors and task outcomes in the database for the admin page, and for how many days |
| `ACCOUNT_EXPORT_TTL_HOURS` | `48` | how long a person's data download stays available before it is deleted |
| `APP_VERSION` | `dev` | shown on the admin page; the production compose file sets it from `TAG` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | unset | send traces to an OpenTelemetry collector |
| `MASTODON_PHOTO_BATCH_SECONDS` | `180` | a burst of photos becomes one post |
| `MASTODON_DIGEST_HOUR_UTC` | `19` | when the daily digest is posted |
| `FEDIVERSE_ALLOW_PRIVATE_HOSTS` | unset | `1` allows http and private addresses (testing against a local instance only) |
| `MAPPING_MAX_IMAGES` | `150` | most images in one map build |
| `MAPPING_MAX_FRAMES_PER_VIDEO` / `MAPPING_VIDEO_FPS` | `60` / `1` | how a video is sampled |
| `MAPPING_TIMEOUT_SECONDS` | `7200` | give up on a build after this long |
| `MAPPING_DETECT_MAX_SHOTS` / `MAPPING_DETECT_MAX_RANGE_M` | `40` / `15` | photos looked at, and how far away an object may be |
| `DETECTOR_MODEL`, `SEGMENTER_MODEL` | Grounding DINO tiny, SAM base | recognition models (downloaded on first use) |

## More documentation

- [docs/plan.md](docs/plan.md): design, data model, every phase and ticket, and what real photos taught us.
- [docs/ci.md](docs/ci.md): workflows, secrets, image tags, local equivalents.
- [docs/mobile.md](docs/mobile.md): the phone app: capture, measuring, design, previewing.

## Licence

No licence has been chosen yet; all rights reserved until one is added.
