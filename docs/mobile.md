# Mobile app (Expo / React Native)

`mobile/` is the field app for Android and iOS: TypeScript, Expo SDK 58, Expo Router. It uses the same API as the web app. Phases and tickets: see "Mobile app" in [plan.md](plan.md) (AM-27 to AM-31, AM-44).

## What exists (AM-27)
- Sign in with a server address, email and password. Tokens and the server address live in the phone's secure storage; an expiring token is refreshed automatically, and only a refused refresh signs the person out (no signal never does).
- Allotment switcher (the last choice is remembered).
- **Offline queue** (`src/queue`): everything the app writes is saved to an SQLite table first and sent when there is signal, oldest first, retrying after 5 s, 30 s, 2 min, 10 min, 30 min, then hourly. A job the server refuses (validation, permission, too large) is parked as failed with the server's reason and a Retry / Discard choice. The queue runs on start-up, every 15 s, and when the app returns to the foreground. Photo and video uploads stream from disk (never loaded into memory) as multipart, with progress.
- `src/api/schema.d.ts` is a copy of the web app's generated types. After the API changes: `npm run gen:api` in `frontend/`, then `npm run gen:api` here (CI checks they match).


## Account (AM-77)
**Account** on the home screen (next to Sign out, `app/account.tsx`) has **Download my data** (asks the server for a zip, checks on it every 2 seconds, then opens the download link in the browser) and **Delete my account** (needs the password, or for an account with no password a confirmation at the single sign-on provider: the app opens the provider's page like a sign-in and the server sends the phone back to `allotment://auth?reauth=<code>`). If the person is the only owner of an allotment shared with others the server refuses and the screen lists them. The App Store and Google Play both require account deletion to be possible inside the app. The calls are in `src/account/client.ts`.

## Guided capture (AM-28)
"Photograph the plot" opens the camera. Unlike the phone's own camera app it reads the **phone's GPS, compass heading and tilt itself** at the moment of each shot and sends them as explicit upload fields (`lat`, `lng`, `heading`, `taken_at`, `capture_session`, `client_id`). The server stores them with `position_source = device`, in preference to the file's EXIF, and the mapping pipeline never treats them as "stuck GPS". The real photo sets that failed taught the coaching in `src/capture/coaching.ts`:
- no fix, or one over 10 s old: the shutter is disabled; a rough fix (over 15 m) only warns;
- a photo within 1 m of the last: "take a step or two" (photos from one spot can't be joined up);
- camera pitched more than 25 degrees above or below the horizon, or no compass: a warning;
- at the end, a summary and plain-language verdict: photos, metres walked, how many of the 12 compass sectors were faced, shots too close together, rough fixes; "Build a map from this walk" is offered once every photo has reached the server (it sends the walk's `capture_session` to `POST /map-jobs`).
Photos are copied into the app's storage, queued, and the copy is deleted after a successful upload. A resent upload carries the same `client_id`, so the server returns the original instead of creating a duplicate.

Not yet checked on a real phone: the compass reading for a camera held upright (it should be the direction the lens faces; confirm by photographing along a known direction), and background behaviour while a long upload runs. Video capture and a GPS track for a phone video are not part of this phase.

## Measure the plot (AM-29, server side AM-17)
"Measure the plot" lists the distances to take. The server makes the list from the shapes drawn on the map ("Make the checklist" / "Update from the map"): a polygon gets its sides plus a diagonal from corner 1 to each non-neighbouring corner (2n-3 distances fix a shape exactly), a line gets one per segment, a circle its radius. Each row opens a screen with a sketch of the shape, the two corners being measured drawn bold, what the map says, and an entry box that understands `3.2`, `320cm`, `10ft 6in` and `10'6"`; **Save and next** goes to the next unmeasured distance. Values are saved at once on screen and sent through the offline queue, so measuring works without signal (making the checklist and applying need to be online). The unit shown (m, cm, ft/in) is a setting of the allotment; the owner picks it.
**Apply to map** previews the correction: the drawn outline dashed, the corrected one solid on the same scale, how far corners move, and warnings (a measurement that disagrees with the others, which probably means a misread; shapes that still need more measurements, whose other corners stay as drawn). Applying is all or nothing and counts as a map edit on the overview. The fit itself is least squares on local metres, pinned to the drawn position so the shape is not shifted, turned or mirrored (`backend/allotment/measure.py`). Adding a spare distance by hand (`POST /measurements`) gives the fit something to check the others against; exactly 2n-3 measurements always fit perfectly, so mistakes only show up when there is a spare.

## Seeds, trays and beds (AM-44)
Three tiles on the home screen, built on the web phases (AM-38, AM-40, AM-41, AM-42):
- **Seeds**: the library with search and a "Sow this month" switch (a packet counts if it can be sown indoors or outdoors that month), packets waiting under "To review", and a packet screen with every field, the 12-month by 4-activity strip (tap a month to flip it) and photos. **Scan a packet** opens the camera; the photo goes through the offline queue as an upload with `read_packet=true`, so the one queued request both stores the photo and has the server read it into a draft (a resent upload carries the same `client_id`, so it is never read twice). The draft screen says what the reader could not find, shows the calendar as it was read, and Save to library makes it active. Saving a packet needs signal (it says so).
- **Seed trays**: a grid you can tap (a row or column number picks the whole line), coloured per kind of seed with a tick for came up and a cross for failed. With cells chosen: Came up, Failed, Back to sown, Clear, or sow a packet with a seed count. Changes show at once and go through the queue, so it works in the greenhouse without signal (`src/trays/model.ts` applies them locally and builds the request). Photos of the tray link to it.
- **Beds**: each bed with what is growing, a sketch of the bed with its planting areas as labelled regions, and for each planting its state (change it with one tap; queued like tray changes) and a photo. Drawing a planting area and planting out a tray are done on the web for now (clicking the corners of an area is a poor fit for a thumb; AM-58 and AM-59 cover better ways).

One camera screen (`app/photo.tsx`) serves all of these: scanning a packet, or a photo of a packet, tray or planting (`?mode=scan`, `?packetId=`, `?trayId=`, `?plantingId=`).

## Jobs (AM-31)
- **Jobs**: the allotment's open tasks under Overdue / Today / Coming up / No date, with a round tick box on each. Ticking shows at once and is queued (`src/tasks/model.ts` builds the request; the server treats a second "complete" as already done). **Add a job** takes a title, when (today, tomorrow, next week, none), priority and where: anywhere, a bed, or "here", which pins it to the phone's position (asks for location permission). A new job appears in the list straight away, marked "Waiting to send" until the server has it (it can't be ticked until then). Each job has a Photo button that opens the camera and attaches the photo to the task. Viewers see the list without tick boxes. The home screen shows how many jobs are due or late.

## Design
Used outdoors, in sun, often with muddy hands, so: strong contrast in both themes (text and buttons all clear 4.5:1; the light theme is the one for bright days), 48 px touch targets, large type, and status always written as words as well as colour. Tokens (colours, type scale, spacing) are in `src/ui/theme.ts`; the shared pieces (screen with back button, cards, list rows, buttons, chips, banners, progress, fields, segmented control, loading/empty states) in `src/ui/kit.tsx`. Screens follow one pattern: a clear title and one line saying what it is for, content in cards, the one action that matters pinned at the bottom. The home screen leads with the allotment's name and the two things you do there; anything waiting to send shows as a banner that opens the Sending screen (retry or discard failures).

**Previewing without a phone.** `EXPO_PUBLIC_DEMO=1 npx expo start --web` runs the app in a browser at phone width against built-in fake data (signed in already; add `?signout` for the sign-in screen, `?light` for the light theme; `/demo?view=hud`, `hud-bad`, `summary`, `summary-bad` show the camera overlay and walk summary, which need a real camera). It does nothing unless that variable is set. Headless Chrome can screenshot any of these addresses for review.

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
# or a cloud development build with EAS: see "Building with EAS" below
```
On the sign-in screen, enter the address the phone can reach. For the development stack that is your computer's LAN IP with the API port (`192.168.1.20:8000`) or the web dev server port (`192.168.1.20:5173`); for a production deployment it is its address (`https://plot.example.com`, or `192.168.1.20:8080` on a home network). `localhost` means the phone itself. Plain `http` is allowed in these builds (and the CI APK) for self-hosted use on a home network; use `https` for anything reachable from the internet. Store builds allow it only for local-network addresses on iOS and for `localhost` and `.local` names on Android; see [store-review.md](store-review.md). An address typed without `http://` or `https://` gets `http://` only if it is on the local network.

## Building the app: which route to use

There are two ways to build, and they are separate. **Nothing in CI calls EAS.**

| | Gradle build (`scripts/build-android.sh`) | EAS Build (Expo's cloud service) |
|---|---|---|
| Triggered by | CI on a `v*` tag or "Run workflow" (see [ci.md](ci.md)), or by hand | **You, by hand**, with the commands below |
| Makes | an Android APK | Android APK or AAB, and **iOS** (needs no Mac) |
| Signed with | the release key in OpenBao (`env/shell/android-signing`), or the debug key without it | a key EAS manages for the project (see "Signing" below) |
| Plain HTTP to a LAN address | allowed (`ALLOW_CLEARTEXT=1` is the script's default) | `development` and `preview` profiles only; not `production` |
| For | installing on your own phones, the CI artifact on ProGet | iOS, TestFlight, and the App Store and Google Play |

## Building the Android app with Gradle
`mobile/scripts/build-android.sh` makes an installable APK with no Expo account (CI runs the same script for release tags: see [ci.md](ci.md)). It is signed with the debug key unless the OpenBao key is supplied, so without that it is for your own phone. `adb install mobile/dist/allotment-<version>-<commit>.apk`, or open the file on the phone.

## Building with EAS
The Expo project is `@daubney-dev/allotment-field` (dashboard: <https://expo.dev/accounts/daubney-dev/projects/allotment-field>). Its ID and owner are in `app.json` (`expo.extra.eas.projectId`, `expo.owner`), and the build profiles are in `mobile/eas.json`.

### 1. Log in: the token comes from OpenBao
Builds run as a robot user with an access token that is kept in OpenBao, in the `expo` group of `envbao`, as `EXPO_TOKEN`. Run every `eas` command inside `envbao exec`, from the `mobile/` directory:

```
cd mobile
envbao exec -q expo -- npx eas-cli whoami      # should name the account (daubney-dev) and say "authenticated using EXPO_TOKEN"
```
`npx eas-cli` needs no install. (In a normal terminal `eas login` also works, as yourself; a script or an agent has no terminal to type into, so it uses the token.) If `whoami` says "Not logged in", the token is not reaching the command: check that the `expo` group in your `envbao` config maps a secret to a variable named exactly `EXPO_TOKEN`.

### 2. Start a build
All of these are run from `mobile/`. Add `--non-interactive` when there is no terminal to answer questions, but see "First build on each platform" first.

```
# An Android APK to install on a phone (like the CI one, but built by Expo):
envbao exec -q expo -- npx eas-cli build --platform android --profile preview

# A development build (the app with its developer tools, for `expo start`):
envbao exec -q expo -- npx eas-cli build --platform android --profile development
envbao exec -q expo -- npx eas-cli build --platform ios --profile development
# (needs the expo-dev-client package, which is in package.json; it needs no store account on Android)

# What goes to the stores (an Android app bundle, an iOS archive), HTTPS only:
envbao exec -q expo -- npx eas-cli build --platform android --profile production
envbao exec -q expo -- npx eas-cli build --platform ios --profile production

# Both platforms at once:
envbao exec -q expo -- npx eas-cli build --platform all --profile production
```
The command uploads the project, queues the build on Expo's servers and prints a link to follow it. By default it then **waits** for the build to finish (it can sit in Expo's queue, then take 10 to 30 minutes); add `--no-wait` to schedule it and return at once. The build runs on Expo's servers either way, so closing the terminal does not stop it. Check on it with:

```
envbao exec -q expo -- npx eas-cli build:list                 # recent builds and their state
envbao exec -q expo -- npx eas-cli build:view <build id>      # one build, with the download link
```
Download the file from that link (or from the dashboard). An Android APK installs by opening it on the phone; an iOS build goes to TestFlight with `eas submit` (below), or, for the `development` profile, installs on registered test devices.

Builds wait in Expo's queue first: on the free plan expect 10 to 30 minutes in `IN_QUEUE`, then 15 to 20 minutes building. Check with `build:view <id>` or `build:list`.

`eas build --local` builds on your own machine instead (Android needs the SDK, iOS needs a Mac with Xcode); it is useful to debug a build that fails in the cloud.

### The profiles (`mobile/eas.json`)
| Profile | For | Output | Plain HTTP |
|---|---|---|---|
| `development` | `expo start` with developer tools | internal-distribution build with the development client | any address (`ALLOW_CLEARTEXT=1`) |
| `preview` | trying a build on phones | Android: an installable **APK**. iOS: an internal build | any address on Android (`ALLOW_CLEARTEXT=1`); local network on iOS |
| `production` | the App Store and Google Play | Android **AAB**, iOS archive; build number goes up by one each build (`autoIncrement`) | **HTTPS only** on Android (plus `localhost` and `.local`); local network on iOS |

`ALLOW_CLEARTEXT` is an environment variable on the profile, read by `mobile/plugins/network-security.js` when the native project is generated. The reasons are in [store-review.md](store-review.md). To see exactly what a profile resolves to: `envbao exec -q expo -- npx eas-cli config --platform android --profile production --non-interactive`.

### First build on each platform
The first build for each platform needs credentials, and EAS asks questions to set them up, so run it **once in a normal terminal** (not with `--non-interactive`):
- **Android**: EAS offers to generate a keystore and keeps it. (With `--non-interactive` it generates one without asking; the first build, a `development` one on 18 November 2026, did exactly that.) See "Signing" below before the first Play upload.
- **iOS**: needs a paid **Apple Developer account**. EAS asks you to sign in to Apple and then creates and stores the certificate and provisioning profile for `dev.daubney.allotment`. A development or preview iOS build also needs the test iPhones registered (`eas device:create`).

Later builds, including `--non-interactive` ones, reuse them.

### Version numbers
- `version` in `app.json` (for example `1.4.1`) is the version people see. **Raise it by hand for a release.** The CI APK file name uses it, and so does the app's check against the server's `MIN_APP_VERSION` ([store-review.md](store-review.md#3-app-and-server-versions)).
- The iOS **build number** and Android **version code** are kept by EAS (`"appVersionSource": "remote"` in `eas.json`) and go up by one on each `production` build. You do not edit them. To see or set them: `eas build:version:get` / `eas build:version:set`.
- The Gradle/CI build does not use these numbers: its Android version code is whatever the generated project says. So an APK from CI and a bundle from EAS are not numbered in the same sequence.

### Signing: the CI key and EAS's key are not the same
The CI build signs with the key in OpenBao (`env/shell/android-signing`). EAS, by default, **generates its own keystore** the first time. An app signed with one key cannot be updated by an APK signed with the other: Android makes the person uninstall first. Decide which you want before the first Play Store upload, because that choice is permanent:
- Let EAS keep the key and use EAS for everything that is distributed (then the CI APK is for your own phones only), or
- Give EAS the existing key instead: `eas credentials --platform android` and choose to upload a keystore (decode `ANDROID_KEYSTORE_B64` from OpenBao to a file for this and delete the file after).
Google Play can also manage the final signing key itself (Play App Signing, the default for new apps); EAS's key then becomes the *upload* key.

### Sending a build to the stores
```
envbao exec -q expo -- npx eas-cli submit --platform ios --profile production --latest       # to TestFlight
envbao exec -q expo -- npx eas-cli submit --platform android --profile production --latest   # to Google Play
```
`--latest` takes the most recent build. These have not been tried yet. Each store needs setting up first: iOS needs the app created in App Store Connect; Android needs a Google Play service-account key given to EAS, and the very first upload of an app must be made by hand in the Play Console. What the stores ask for (review notes, privacy, data safety) is in [store-review.md](store-review.md) and AM-63.

### Triggering builds from CI
Not set up. The Gitea `mobile` workflow builds the Android APK with Gradle and never calls EAS. To add it, a step would run `npx eas-cli build --non-interactive --platform ios --profile production` with `EXPO_TOKEN` supplied from OpenBao (as `BAO_CI_TOKEN` is for the signing key), after the first interactive build has created the iOS credentials.

### If a build fails
- `eas build:view <id>` links to the build logs on expo.dev; the failing step is usually named there.
- `npx expo prebuild --platform android --clean --no-install` (or `ios`) in `mobile/` reproduces the native project generation locally, which is where config plugin mistakes show up. The folders it writes (`android/`, `ios/`) are not committed. It also rewrites two scripts in `package.json`; discard that change with `git checkout package.json`.
- A build that does not appear in `build:list` was probably not started: look for an error from the command, such as "Not logged in".

## Checks
`npm run typecheck`, `npm test` (Jest: session, queue, request handlers, version check, the Android network config plugin), and `npx expo export` (bundling) run in CI as the `mobile` job. Sensors, camera, background transfer and the native screens can only be checked on a device or simulator.

## Not yet
Video capture, boundary trace (AM-30), the read-only map and recent activity from AM-31, drawing planting areas and planting out on the phone. Store submission is set up (EAS profiles, review notes in [store-review.md](store-review.md)) but no build has been submitted yet (AM-63).
