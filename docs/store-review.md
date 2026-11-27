# Store review notes (AM-112, part of AM-63)

How to build and submit with EAS is in [mobile.md](mobile.md#building-with-eas). This page is what the stores ask for.

What an App Store or Google Play reviewer needs, and the answers to what they will ask. The app is a
client for a server the person runs themselves, so a reviewer cannot use it without one.

## 1. Something to review against: a demo server

Reviewers must be able to sign in. Run a demo server (the normal stack, see the README) on a public
HTTPS address and give them its address and a ready-made account in the review notes.

- Seed it with `docs/screenshots/demo_seed.py` (it registers an account, makes a plot with beds, jobs
  and seed packets). Point `BASE` at the demo server, and register a **fixed** reviewer email and password
  rather than a random one, so the notes stay valid.
- Keep the demo server's registration closed (`REGISTRATION=invite`) so it stays a demo.
- Reset it between submissions: reviewers may delete the account (that is a required feature, AM-77).
  Re-run the seed script afterwards.

Text for the review notes (fill in the placeholders; do not commit real credentials):

> Allotment connects to a server that the user hosts. To try the app, enter this server address on the
> sign-in screen: `https://<demo server>`, and sign in with email `<reviewer email>` and password
> `<reviewer password>`. The account has a sample allotment. Account deletion and data export are under
> Account on the home screen.

`EXPO_PUBLIC_DEMO` stays a developer tool for browser previews and screenshots. It is not a reviewer path.

## 2. Plain HTTP

People self-host on a home network, so the app has to be able to reach `http://192.168.x.x:8000`. The two
platforms differ in what they can express, so the builds differ:

| Build | Android | iOS |
| --- | --- | --- |
| Store (EAS `production`) | HTTPS only, except `localhost`, `10.0.2.2` and `*.local` names | HTTPS only, except local-network addresses (`NSAllowsLocalNetworking`) |
| Sideloaded APK (CI, EAS `development` and `preview`) | Plain HTTP anywhere (`ALLOW_CLEARTEXT=1`) | As the store build |

Android cannot allow plain HTTP for an address range, only for named hosts, so the Play build cannot reach
a server at a bare LAN address such as `192.168.1.5` over HTTP. Those users either put a certificate on
their server (any `https://` address works) or use a `.local` name, or install the APK from CI, which allows
it. The app also defaults to `https://` when the address typed has no scheme, unless it is clearly on the
local network (see `normaliseServerUrl` in `mobile/src/auth/session.ts`).

The Android switch is the config plugin `mobile/plugins/network-security.js`.

### Justification for Apple (App Transport Security)

The app sets only `NSAllowsLocalNetworking`; it does **not** use `NSAllowsArbitraryLoads`. Text for the
App Review notes if asked:

> Allotment is a client for a server that each user runs themselves, often on their home network at an
> address like 192.168.1.20 or `plot.local`, where no public certificate can be issued. We use
> NSAllowsLocalNetworking so the app can reach a server on the user's own local network over HTTP. Every
> other connection is subject to App Transport Security, and servers reachable from the internet need
> HTTPS. We do not disable ATS globally.

## 3. App and server versions

The app and server release separately, so each says when the other must update. The phone app reads the
unauthenticated `GET /api/v1/auth/config` (on the sign-in screen and, once signed in, on the home screen):

- `min_app_version` (server setting `MIN_APP_VERSION`, default `0.0.0`): the oldest app it works with. An
  older app shows "update the app".
- `api_level` (`API_LEVEL` in `backend/allotment/config.py`) against `REQUIRED_API_LEVEL` in
  `mobile/src/auth/compat.ts`: if the server's level is lower than the app needs, the app shows "update the
  server". A server that reports no level predates the check and counts as 0.
- `server_version` is the release the server is running.

When a change lets an old server no longer serve a new app, raise **both** constants together in that
change. When a server change breaks old apps, raise `MIN_APP_VERSION` to the first app version that copes.
Version numbers on the stores (iOS build number, Android version code) are managed by EAS
(`appVersionSource: remote`, `autoIncrement` on the production profile).
