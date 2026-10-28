# Mobile app (Expo / React Native)

`mobile/` is the field app for Android and iOS: TypeScript, Expo SDK 58, Expo Router. It uses the same API as the web app. Phases and tickets: see "Mobile app" in [plan.md](plan.md) (AM-27 to AM-31).

## What exists (AM-27)
- Sign in with a server address, email and password. Tokens and the server address live in the phone's secure storage; an expiring token is refreshed automatically, and only a refused refresh signs the person out (no signal never does).
- Allotment switcher (the last choice is remembered).
- **Offline queue** (`src/queue`): everything the app writes is saved to an SQLite table first and sent when there is signal, oldest first, retrying after 5 s, 30 s, 2 min, 10 min, 30 min, then hourly. A job the server refuses (validation, permission, too large) is parked as failed with the server's reason and a Retry / Discard choice. The queue runs on start-up, every 15 s, and when the app returns to the foreground. Photo and video uploads stream from disk (never loaded into memory) as multipart, with progress.
- `src/api/schema.d.ts` is a copy of the web app's generated types. After the API changes: `npm run gen:api` in `frontend/`, then `npm run gen:api` here (CI checks they match).


## Guided capture (AM-28)
"Photograph the plot" opens the camera. Unlike the phone's own camera app it reads the **phone's GPS, compass heading and tilt itself** at the moment of each shot and sends them as explicit upload fields (`lat`, `lng`, `heading`, `taken_at`, `capture_session`, `client_id`). The server stores them with `position_source = device`, in preference to the file's EXIF, and the mapping pipeline never treats them as "stuck GPS". The real photo sets that failed taught the coaching in `src/capture/coaching.ts`:
- no fix, or one over 10 s old: the shutter is disabled; a rough fix (over 15 m) only warns;
- a photo within 1 m of the last: "take a step or two" (photos from one spot can't be joined up);
- camera pitched more than 25 degrees above or below the horizon, or no compass: a warning;
- at the end, a summary and plain-language verdict: photos, metres walked, how many of the 12 compass sectors were faced, shots too close together, rough fixes; "Build a map from this walk" is offered once every photo has reached the server (it sends the walk's `capture_session` to `POST /map-jobs`).
Photos are copied into the app's storage, queued, and the copy is deleted after a successful upload. A resent upload carries the same `client_id`, so the server returns the original instead of creating a duplicate.

Not yet checked on a real phone: the compass reading for a camera held upright (it should be the direction the lens faces; confirm by photographing along a known direction), and background behaviour while a long upload runs. Video capture and a GPS track for a phone video are not part of this phase.

## Running it
```
docker compose up -d                 # the API, from the repo root
cd mobile && npm install
npx expo start                       # scan the QR code with Expo Go, or press i / a for a simulator
```
Expo Go can run this shell. Later phases use native sensors and background location, which need a **development build**:
```
npx expo prebuild                     # generates ios/ and android/ (not committed)
npx expo run:android                  # or run:ios (macOS + Xcode)
# or cloud builds: npm i -g eas-cli && eas build --profile development --platform all
```
On the sign-in screen, enter the address the phone can reach: your computer's LAN IP and the web port (`192.168.1.20:8080`) or the API port (`192.168.1.20:8000`). `localhost` means the phone itself. Plain `http` is allowed in these builds for self-hosted use on a home network; use `https` for anything reachable from the internet.

## Checks
`npm run typecheck`, `npm test` (Jest: session, queue, request handlers), and `npx expo export` (bundling) run in CI as the `mobile` job. Sensors, camera, background transfer and the native screens can only be checked on a device or simulator.

## Not yet
Video capture, Measure (AM-29), boundary trace (AM-30), tasks and quick photos (AM-31), app store distribution.
