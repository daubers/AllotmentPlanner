# CI (Gitea Actions)

| Workflow | Trigger | What it does |
|---|---|---|
| `.gitea/workflows/test.yml` | every push and PR | ruff lint and format check, pytest with coverage, frontend and phone app checks, `docker compose config` validation of the dev and production (`make prod-config`) files |
| `.gitea/workflows/build.yml` | push to `main`, tags `v*` | repeats pytest, then builds the `prod` image target and pushes it to the Gitea container registry |

## Runner requirements
An `act_runner` labelled `ubuntu-latest` with access to the Docker socket (needed for buildx).

## Secrets
- `REGISTRY_TOKEN`: a personal access token with `write:package`. The automatic `GITEA_TOKEN` usually cannot push packages.
- `DEPLOY_DISPATCH_TOKEN`: a personal access token that can dispatch workflows on `matt/Allotment-Deploy` (used by the `trigger-deploy` job).

## Image tags
Three images are pushed to `<gitea-host>/<owner>/`: `allotment-api`, `allotment-frontend` and `allotment-worker` (the OpenSfM + GDAL mapping worker). Each gets `sha-<short>`, the branch name, `latest` on `main`, and `X.Y.Z` / `X.Y` for tags like `v0.1.0`.

The worker image compiles OpenSfM from a pinned commit in a build stage (about 5 minutes on the runner, every time, and roughly 4 GB of RAM). Its layers are deliberately small and its cache is exported with `mode=min`: the registry sits behind an nginx that answers `413 Request Entity Too Large` to blobs above somewhere between 164 MB and 498 MB (compressed), so the build stage's large layers must never be uploaded. If you raise `client_max_body_size` on that nginx, the worker can use `mode=max` like the others and skip the recompile. The mapping pipeline itself is checked locally with `make mapping-check`, not in CI, because it needs that image.
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

## Deploying what CI builds
`deploy/docker-compose.prod.yml` runs these images; the README's "Deployment" section is the walk-through (settings, first start, TLS, backups, upgrades). The `api` image contains the database migrations, and a one-shot `migrate` service runs `flask db upgrade` before anything else starts.

## Automatic deployment
Pushing a plain `vX.Y.Z` tag on a commit that is on `main` deploys it to the production host. After `build` pushes the images, its `trigger-deploy` job waits for the `test` workflow on the same tag, then dispatches the `deploy` workflow in `matt/Allotment-Deploy`, which re-checks that the commit is on `main` and that `build` and `test` both succeeded, then runs the Ansible playbook. Pre-release tags such as `v1.0.0-rc1` are built but not deployed. Roll back by running the `deploy` workflow by hand with an older tag.
