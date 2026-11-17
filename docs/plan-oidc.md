# Plan: OIDC sign-in (alongside passwords)

## Context
Login today is email+password only (`backend/allotment/api/auth.py`, JWT access/refresh via flask-jwt-extended). `User.password_hash` is non-null and there is no external identity table. Registration is invite-only in production (`REGISTRATION=invite`), and the web app and API are served from one origin (nginx proxies `/api`).

## Decisions
- Providers: **both** a generic configurable OIDC issuer (Authentik/Keycloak/Authelia etc.) and presets for public providers (Google, Microsoft); several can be enabled at once.
- OIDC is **alongside** password login; nothing existing is removed.
- Provisioning: **existing or invited users only**. Match by verified email, or honour an invite code. No auto-created accounts, so invite-only stays intact.
- **Web and mobile together.**

## Design
- **Library:** add `authlib` (OIDC discovery, PKCE, ID-token validation) to `backend/pyproject.toml`; it uses the already-present `requests`.
- **Config** (`config.py`): `OIDC_PROVIDERS` as a JSON env or numbered env set; per provider `id`, `name`, `issuer` (discovery URL) or a preset name, `client_id`, `client_secret`, `scopes` (default `openid email profile`). Secrets go in the deploy repo (`AllotmentDeploy` `.env` template and Actions secrets), never in git.
- **Data:** new table `oidc_identities` (`user_id` FK cascade, `provider`, `subject`, `email`, `created_at`, unique `(provider, subject)`), with a migration chained after the current head (or the task-comments migration if it lands first). `password_hash` becomes nullable for OIDC-only users, and `verify_password` (`security.py:18`) must return False for a null hash.
- **Flow** (new `api/oidc.py`, blueprint under `/api/v1/auth/oidc`):
  1. `GET /providers` lists providers for the login page (extend `AuthConfigSchema`, `auth.py:37`).
  2. `GET /<provider>/login?client=web|mobile&invite=<code>` creates state, nonce and PKCE verifier (Redis, short TTL) and 302s to the IdP.
  3. `GET /<provider>/callback` exchanges the code and validates the ID token (issuer, audience, nonce, expiry). Require `email_verified`. Resolve the user: existing identity -> that user; else existing user with that email -> link identity; else valid invite for that email -> create user + membership (reusing `read_invite` and the register logic in `auth.py:49-81`); else 403. Emit `user.logged_in` (and `user.registered` / `member.added` when applicable).
  4. Never put JWTs in a URL: redirect to the web app or mobile deep link with a **one-time code** (Redis, about 60 s, single use); `POST /auth/oidc/exchange` returns the same `TokenSchema` as `/login` (`_tokens`, `auth.py:28`).
- **Web:** "Sign in with ..." buttons on `pages/Login.tsx`, an exchange step in `auth.tsx`, and an `/auth/callback` route that handles the code; the invite-link flow carries the code through.
- **Mobile:** `expo-auth-session` + `expo-web-browser` (add to `mobile/package.json`; app-scheme redirect), opening `/api/v1/auth/oidc/<p>/login?client=mobile` and exchanging the returned code through `Session` (`mobile/src/auth/session.ts`), storing tokens as today. Redirect URIs are an allow-list on the server.
- **Security:** exact redirect-URI allow-list; state + nonce + PKCE; single-use short-lived codes; link-by-email only when `email_verified` is true; rate limit callback/exchange like login; log failures as `user.login_failed` events.
- **Deploy:** add env vars to the `roles/allotment` template in `AllotmentDeploy`; register the redirect URI(s) at each IdP.
- **Docs:** README "Who can sign up" section and a user-facing `docs/oidc.md` once built.

## Tests
- Backend: mock the IdP (discovery + token + JWKS) in `backend/tests/test_oidc.py`: existing-user link, invited-user create, unknown email 403, unverified email refused, bad state/nonce, code reuse, password login unaffected, null-password user cannot password-login.
- Frontend (vitest) for the callback/exchange; mobile jest for the session exchange; one e2e using a stub IdP if practical.

## Verification
Run the stack with a local IdP container (Authentik/Keycloak or a mock OIDC server), sign in on web and from the Expo app, confirm an uninvited account is rejected and that existing password login still works. `make test` plus the frontend and mobile suites.

## Open items
- Exact preset list (Google, Microsoft) and whether Microsoft's multi-tenant issuer needs special handling.
- Letting a signed-in user link/unlink identities from a settings page (not in the first cut).