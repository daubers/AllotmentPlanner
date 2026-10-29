# Mobile app (Expo / React Native)

`mobile/` is the field app for Android and iOS: TypeScript, Expo SDK 58, Expo Router. It uses the same API as the web app. Phases and tickets: see "Mobile app" in [plan.md](plan.md) (AM-27 to AM-31, AM-44).

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

## Measure the plot (AM-29, server side AM-17)
"Measure the plot" lists the distances to take. The server makes the list from the shapes drawn on the map ("Make the checklist" / "Update from the map"): a polygon gets its sides plus a diagonal from corner 1 to each non-neighbouring corner (2n-3 distances fix a shape exactly), a line gets one per segment, a circle its radius. Each row opens a screen with a sketch of the shape, the two corners being measured drawn bold, what the map says, and an entry box that understands `3.2`, `320cm`, `10ft 6in` and `10'6"`; **Save and next** goes to the next unmeasured distance. Values are saved at once on screen and sent through the offline queue, so measuring works without signal (making the checklist and applying need to be online). The unit shown (m, cm, ft/in) is a setting of the allotment; the owner picks it.
**Apply to map** previews the correction: the drawn outline dashed, the corrected one solid on the same scale, how far corners move, and warnings (a measurement that disagrees with the others, which probably means a misread; shapes that still need more measurements, whose other corners stay as drawn). Applying is all or nothing and counts as a map edit on the overview. The fit itself is least squares on local metres, pinned to the drawn position so the shape is not shifted, turned or mirrored (`backend/allotment/measure.py`). Adding a spare distance by hand (`POST /measurements`) gives the fit something to check the others against; exactly 2n-3 measurements always fit perfectly, so mistakes only show up when there is a spare.

## Seeds, trays and beds (AM-44)
Three tiles on the home screen, built on the web phases (AM-38, AM-40, AM-41, AM-42):
- **Seeds**: the library with search and a "Sow this month" switch (a packet counts if it can be sown indoors or outdoors that month), packets waiting under "To review", and a packet screen with every field, the 12-month by 4-activity strip (tap a month to flip it) and photos. **Scan a packet** opens the camera; the photo goes through the offline queue as an upload with `read_packet=true`, so the one queued request both stores the photo and has the server read it into a draft (a resent upload carries the same `client_id`, so it is never read twice). The draft screen says what the reader could not find, shows the calendar as it was read, and Save to library makes it active. Saving a packet needs signal (it says so).
- **Seed trays**: a grid you can tap (a row or column number picks the whole line), coloured per kind of seed with a tick for came up and a cross for failed. With cells chosen: Came up, Failed, Back to sown, Clear, or sow a packet with a seed count. Changes show at once and go through the queue, so it works in the greenhouse without signal (`src/trays/model.ts` applies them locally and builds the request). Photos of the tray link to it.
- **Beds**: each bed with what is growing, a sketch of the bed with its planting areas as labelled regions, and for each planting its state (change it with one tap; queued like tray changes) and a photo. Drawing a planting area and planting out a tray are done on the web for now (clicking the corners of an area is a poor fit for a thumb; AM-58 and AM-59 cover better ways).

One camera screen (`app/photo.tsx`) serves all of these: scanning a packet, or a photo of a packet, tray or planting (`?mode=scan`, `?packetId=`, `?trayId=`, `?plantingId=`).

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
# or cloud builds: npm i -g eas-cli && eas build --profile development --platform all
```
On the sign-in screen, enter the address the phone can reach. For the development stack that is your computer's LAN IP with the API port (`192.168.1.20:8000`) or the web dev server port (`192.168.1.20:5173`); for a production deployment it is its address (`https://plot.example.com`, or `192.168.1.20:8080` on a home network). `localhost` means the phone itself. Plain `http` is allowed in these builds for self-hosted use on a home network; use `https` for anything reachable from the internet.

## Checks
`npm run typecheck`, `npm test` (Jest: session, queue, request handlers), and `npx expo export` (bundling) run in CI as the `mobile` job. Sensors, camera, background transfer and the native screens can only be checked on a device or simulator.

## Not yet
Video capture, boundary trace (AM-30), tasks and quick photos (AM-31), drawing planting areas and planting out on the phone, app store distribution.
