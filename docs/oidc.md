# Single sign-on (OpenID Connect)

Optional "Sign in with ..." buttons on the web login page and in the phone app, next to the email and
password login (which stays). Any standards-compliant OpenID Connect provider works (Authentik, Keycloak,
Authelia, Pocket ID, ...), and there are presets for Google and Microsoft. Nothing changes until you
configure a provider.

## Who can sign in

A provider sign-in never creates an account by itself, so an invite-only server stays invite-only. It works for:

1. **Someone who signed in this way before.** They are matched by the provider's stable id for them, so a
   changed email address does not matter.
2. **Someone who already has an account**, if the provider says their email is **verified**. The first time,
   the provider is linked to that account. An unverified email is refused: otherwise anyone could take over an
   account by registering its address at a provider that does not check.
3. **Someone holding an invite** (Settings → Invite someone) for the email the provider reports. The invite
   link carries through the sign-in, and they get an account (with no password) and their role on that allotment.

Anyone else is turned away with a message on the login page. People created this way have no password and
sign in through the provider (there is no password reset for them).

## Setting up

1. At your provider, create an OpenID Connect / OAuth2 **client** (confidential, authorization code flow) and
   register this **redirect URI**, with your own address and the provider's `id` from step 2:

   ```
   https://plot.example.com/api/v1/auth/oidc/<id>/callback
   ```
2. In the server's `.env` (see `deploy/.env.production.example`) set `PUBLIC_URL` and `OIDC_PROVIDERS`, a JSON
   list on one line:

   ```
   PUBLIC_URL=https://plot.example.com
   OIDC_PROVIDERS=[{"id":"authentik","name":"Authentik","issuer":"https://auth.example.com/application/o/allotment/","client_id":"...","client_secret":"..."},{"preset":"google","client_id":"...","client_secret":"..."}]
   ```

   | Field | Meaning |
   |---|---|
   | `id` | short name used in the URLs (lower case); defaults to the preset's name |
   | `name` | the button's label ("Sign in with ...") |
   | `issuer` | the provider's issuer URL; `/.well-known/openid-configuration` is found under it |
   | `preset` | `google`, or `microsoft` (which also needs `tenant`: a tenant id, `organizations` or `consumers`, not `common`) |
   | `client_id`, `client_secret` | from step 1 |
   | `scopes` | optional; default `openid email profile` |

   An incomplete entry is skipped with a warning in the log; it does not stop the server.
3. Restart the `api` service. The login page now shows the buttons.

`PUBLIC_URL` matters behind a reverse proxy: the redirect URI sent to the provider is built from it, and it
must match what you registered exactly.

## The phone app

The app opens the provider's page in the system browser sheet and is sent back to `allotment://auth`. That link
must be allowed by the server: it is by default, and `OIDC_MOBILE_REDIRECTS` (comma separated) changes the list.
The app asks the server which providers it offers, so a server with none shows no buttons.
This needs a build that includes `expo-web-browser`; an app built before this release shows only the password login.

## How it works (and why it is safe)

Authorization code flow with PKCE, a per-sign-in `state` and `nonce`, and the ID token's signature, issuer,
audience and expiry checked against the provider's published keys (asymmetric algorithms only).

- `GET /api/v1/auth/oidc/<id>/login` starts it. The `state` is a signed, ten-minute token, and a random value in
  an `HttpOnly` cookie ties the sign-in to the browser that began it, so a link someone else started cannot be
  finished in your browser.
- `GET /api/v1/auth/oidc/<id>/callback` finishes it and redirects with a **one-time code**, never with tokens in
  the address. `POST /api/v1/auth/oidc/exchange` swaps the code for the app's own tokens. The code works once,
  for a minute, and only its hash is stored.
- Failed sign-ins are logged and recorded as `user.login_failed` events with a reason.

## Not done yet

- Linking or unlinking a provider from a signed-in account (a first sign-in links by verified email).
- Rate limiting on these endpoints (the password login has none either).
