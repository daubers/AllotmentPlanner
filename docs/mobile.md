# Mobile app (Expo / React Native)

`mobile/` is the field app for Android and iOS: TypeScript, Expo SDK 58, Expo Router. It uses the same API as the web app. Phases and tickets: see "Mobile app" in [plan.md](plan.md) (AM-27 to AM-31).

## What exists (AM-27)
- Sign in with a server address, email and password. Tokens and the server address live in the phone's secure storage; an expiring token is refreshed automatically, and only a refused refresh signs the person out (no signal never does).
- Allotment switcher (the last choice is remembered).
- **Offline queue** (`src/queue`): everything the app writes is saved to an SQLite table first and sent when there is signal, oldest first, retrying after 5 s, 30 s, 2 min, 10 min, 30 min, then hourly. A job the server refuses (validation, permission, too large) is parked as failed with the server's reason and a Retry / Discard choice. The queue runs on start-up, every 15 s, and when the app returns to the foreground. Photo and video uploads stream from disk (never loaded into memory) as multipart, with progress.
- `src/api/schema.d.ts` is a copy of the web app's generated types. After the API changes: `npm run gen:api` in `frontend/`, then `npm run gen:api` here (CI checks they match).

Known limitation: an upload that reaches the server but whose reply is lost will be sent again, giving a duplicate photo. AM-28 adds a client id to `POST /media` so the server can ignore repeats.

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
Camera and sensors (AM-28), Measure (AM-29), boundary trace (AM-30), tasks and quick photos (AM-31), app store distribution.
