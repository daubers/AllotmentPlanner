# CI (Gitea Actions)

| Workflow | Trigger | What it does |
|---|---|---|
| `.gitea/workflows/test.yml` | every push and PR | ruff lint and format check, pytest with coverage, frontend and phone app checks, `docker compose config` validation of the dev and production (`make prod-config`) files |
| `.gitea/workflows/build.yml` | push to `main`, tags `v*` | builds the three images and pushes them to the `allotment` Docker feed on ProGet (in parallel with `test.yml`); on a release tag, waits for `test.yml` to pass and starts the deploy |
| `.gitea/workflows/mobile.yml` | tags `v*`, or run by hand | builds the Android app (an installable APK, about 10 to 20 minutes) and keeps it as the `allotment-android` artifact; also repeats the phone app's type check and tests |

## Runner requirements
An `act_runner` labelled `ubuntu-latest` with access to the Docker socket (needed for buildx).

## Secrets
- `PKGS_API_KEY`: the ProGet API key (login user `api`), used to push images to `pkgs.daubney.dev/allotment/`. The same secret is set on Allotment-Deploy to pull them. It is stored in OpenBao and read with `envbao exec -q pkgs`.
- `DEPLOY_DISPATCH_TOKEN`: a personal access token that can dispatch workflows on `matt/Allotment-Deploy` (used by the `trigger-deploy` job).

## Image tags
Three images are pushed to `pkgs.daubney.dev/allotment/`: `allotment-api`, `allotment-frontend` and `allotment-worker` (the OpenSfM + GDAL mapping worker). Each gets `sha-<short>`, the branch name, `latest` on `main`, and `X.Y.Z` / `X.Y` for tags like `v0.1.0`.

The worker image compiles OpenSfM from a pinned commit in a build stage (about 5 minutes without a cache, and roughly 4 GB of RAM). Its build cache is exported with `mode=max` to `allotment-worker:buildcache`, so a rebuild reuses the compiled stage. That needs the nginx in front of ProGet to allow big uploads: `client_max_body_size 0;` with `proxy_request_buffering off;`, `proxy_buffering off;` and long proxy timeouts. Without it every blob over a few hundred MB gets `413 Request Entity Too Large` (build 1019, and the old Gitea registry before that); if you see that again, set `cache_mode: min` on the worker in `build.yml`. The mapping pipeline itself is checked locally with `make mapping-check`, not in CI, because it needs that image.
Release with `git tag v0.1.0 && git push origin v0.1.0`.

## The Android app
`mobile/scripts/build-android.sh` does the whole build (Expo prebuild, then Gradle `assembleRelease`) and CI runs exactly that, so a local run reproduces CI: it needs Node 22, JDK 17 and the Android SDK with its licences accepted. By default only `arm64-v8a` is built (every modern phone; all four architectures take about three times as long): `ANDROID_ABIS=arm64-v8a,x86_64` adds the emulator's. The APK is signed with Expo's debug key, so it installs on your own phone but cannot go to the Play Store. The workflow needs the runner to reach the internet (Gradle, the Android SDK, npm) and uses `actions/upload-artifact@v3` because Gitea's artifact server does not speak the v4 protocol. iOS is not built in CI: it needs a macOS runner and an Apple developer account. What publishing needs, store by store, is AM-63.

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
