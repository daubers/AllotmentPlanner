# CI (Gitea Actions)

| Workflow | Trigger | What it does |
|---|---|---|
| `.gitea/workflows/test.yml` | every push and PR | ruff lint and format check, pytest with coverage, `docker compose config` validation |
| `.gitea/workflows/build.yml` | push to `main`, tags `v*` | repeats pytest, then builds the `prod` image target and pushes it to the Gitea container registry |

## Runner requirements
An `act_runner` labelled `ubuntu-latest` with access to the Docker socket (needed for buildx).

## Secrets
- `REGISTRY_TOKEN`: a personal access token with `write:package`. The automatic `GITEA_TOKEN` usually cannot push packages.

## Image tags
Three images are pushed to `<gitea-host>/<owner>/`: `allotment-api`, `allotment-frontend` and `allotment-worker` (the OpenSfM + GDAL mapping worker). Each gets `sha-<short>`, the branch name, `latest` on `main`, and `X.Y.Z` / `X.Y` for tags like `v0.1.0`.

The worker image compiles OpenSfM from a pinned commit, which takes 15-30 minutes the first time and needs roughly 4 GB of RAM on the runner. The registry build cache (`:buildcache`) keeps later builds to a couple of minutes unless the Dockerfile's OpenSfM layers change. The mapping pipeline itself is checked locally with `make mapping-check`, not in CI, because it needs that image.
Release with `git tag v0.1.0 && git push origin v0.1.0`.

## Local equivalents
```
ruff check backend && ruff format --check backend
(cd backend && pytest -q)
docker build --target prod backend
```

## End-to-end tests (local only for now)
`make e2e` starts the compose stack and runs the Playwright suite in `e2e/` inside the official
Playwright image, attached to the compose network (browser hits `http://frontend:5173`).
It registers a user, draws a bed with the Geoman toolbar, pins a task to it and completes it,
prints the Today sheet, and uploads EXIF-dated photos (processed by the real Celery worker) into the
timeline and before/after slider. It needs the `worker` service running (`make e2e` starts the stack).
Running it in CI needs the job to reach a Docker daemon with bind-mountable paths; that is planned
with the polish phase (AM-10). Test users are named `e2e-*@example.com`.
