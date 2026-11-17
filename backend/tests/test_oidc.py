import json
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest
import responses
from joserfc import jwt
from joserfc.jwk import RSAKey

from allotment import events, sso
from allotment.config import parse_oidc_providers
from allotment.extensions import db
from allotment.invites import make_invite
from allotment.models import Membership, OidcIdentity, OidcLoginCode, User

ISSUER = "https://idp.test"
CLIENT_ID = "allotment-client"
KEY = RSAKey.generate_key(2048, {"kid": "k1"})
OTHER_KEY = RSAKey.generate_key(2048, {"kid": "k1"})  # same kid, different key
BINDER = "oidc_binder"


@pytest.fixture(autouse=True)
def idp(app):
    """An identity provider that answers discovery, key and token requests."""
    sso.clear_discovery_cache()
    app.config["OIDC_PROVIDERS"] = [
        {
            "id": "idp",
            "name": "Test IdP",
            "issuer": ISSUER,
            "client_id": CLIENT_ID,
            "client_secret": "s3cret",
            "scopes": "openid email profile",
        }
    ]
    app.config["PUBLIC_URL"] = "https://plot.test"
    state = {"claims": {}, "key": KEY, "token_requests": []}

    def token(request):
        state["token_requests"].append(request.body)
        now = int(time.time())
        claims = {
            "iss": ISSUER,
            "aud": CLIENT_ID,
            "sub": "sub-1",
            "email": "ann@example.com",
            "email_verified": True,
            "name": "Ann",
            "iat": now,
            "exp": now + 300,
            **state["claims"],
        }
        id_token = jwt.encode({"alg": "RS256", "kid": "k1"}, claims, state["key"])
        body = {
            "access_token": "at",
            "token_type": "Bearer",
            "expires_in": 300,
            "id_token": id_token,
        }
        return 200, {}, json.dumps(body)

    with responses.RequestsMock(assert_all_requests_are_fired=False) as mock:
        mock.get(
            f"{ISSUER}/.well-known/openid-configuration",
            json={
                "issuer": ISSUER,
                "authorization_endpoint": f"{ISSUER}/authorize",
                "token_endpoint": f"{ISSUER}/token",
                "jwks_uri": f"{ISSUER}/jwks",
                "token_endpoint_auth_methods_supported": ["client_secret_basic"],
            },
        )
        mock.get(f"{ISSUER}/jwks", json={"keys": [KEY.as_dict(private=False)]})
        mock.add_callback(responses.POST, f"{ISSUER}/token", callback=token)
        yield state


def begin(client, query="", provider="idp"):
    """Start a sign-in; returns the provider's authorize URL parameters."""
    resp = client.get(f"/api/v1/auth/oidc/{provider}/login{query}")
    assert resp.status_code == 302, resp.get_data(as_text=True)
    url = urlparse(resp.headers["Location"])
    return resp, {k: v[0] for k, v in parse_qs(url.query).items()}, url


def finish(client, params, idp, claims=None, **query):
    """The provider sends the browser back; returns the redirect's (path-or-url, params)."""
    idp["claims"] = {"nonce": params["nonce"], **(claims or {})}
    query = {"code": "provider-code", "state": params["state"], **query}
    resp = client.get("/api/v1/auth/oidc/idp/callback", query_string=query)
    assert resp.status_code == 302
    target = resp.headers["Location"]
    return target, {k: v[0] for k, v in parse_qs(urlparse(target).query).items()}


def sign_in(client, idp, claims=None, query=""):
    _, params, _ = begin(client, query)
    return finish(client, params, idp, claims)


def user(email="ann@example.com", password="password123", name="Ann"):
    from allotment.security import hash_password

    row = User(email=email, display_name=name, password_hash=hash_password(password))
    db.session.add(row)
    db.session.commit()
    return row


def exchange(client, code):
    return client.post("/api/v1/auth/oidc/exchange", json={"code": code})


def test_providers_are_listed_without_secrets(client):
    body = client.get("/api/v1/auth/config").json
    assert body["oidc"] == [{"id": "idp", "name": "Test IdP"}]
    assert "s3cret" not in json.dumps(body)


def test_login_sends_the_browser_to_the_provider_with_pkce(client):
    resp, params, url = begin(client)
    assert f"{url.scheme}://{url.netloc}{url.path}" == f"{ISSUER}/authorize"
    assert params["response_type"] == "code"
    assert params["client_id"] == CLIENT_ID
    assert params["redirect_uri"] == "https://plot.test/api/v1/auth/oidc/idp/callback"
    assert params["code_challenge_method"] == "S256" and params["code_challenge"]
    assert {"openid", "email", "profile"} <= set(params["scope"].split())
    assert params["state"] and params["nonce"]
    cookie = resp.headers["Set-Cookie"]
    assert BINDER in cookie and "HttpOnly" in cookie and "SameSite=Lax" in cookie


def test_unknown_provider_and_bad_client(client):
    assert client.get("/api/v1/auth/oidc/nope/login").status_code == 404
    assert client.get("/api/v1/auth/oidc/idp/login?client=desktop").status_code == 422


def test_a_verified_email_signs_in_an_existing_user_and_links_the_identity(client, idp):
    ann = user()
    target, params = sign_in(client, idp)
    assert target.startswith("/auth/callback?") and "error" not in params
    resp = exchange(client, params["code"])
    assert resp.status_code == 200
    assert resp.json["user"]["email"] == "ann@example.com"
    me = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {resp.json['access_token']}"}
    )
    assert me.json["id"] == ann.id
    link = db.session.query(OidcIdentity).one()
    assert (link.user_id, link.provider, link.subject) == (ann.id, "idp", "sub-1")


def test_the_pkce_verifier_is_sent_to_the_token_endpoint(client, idp):
    user()
    sign_in(client, idp)
    assert "code_verifier=" in idp["token_requests"][0]
    assert "grant_type=authorization_code" in idp["token_requests"][0]


def test_a_linked_identity_signs_in_by_subject_even_if_the_email_changes(client, idp):
    ann = user()
    exchange(client, sign_in(client, idp)[1]["code"])
    target, params = sign_in(client, idp, {"email": "new@example.com", "email_verified": False})
    assert "error" not in params
    assert exchange(client, params["code"]).json["user"]["id"] == ann.id


def test_the_code_works_once(client, idp):
    user()
    code = sign_in(client, idp)[1]["code"]
    assert exchange(client, code).status_code == 200
    assert exchange(client, code).status_code == 401
    assert exchange(client, "made-up").status_code == 401


def test_an_expired_code_is_refused(client, idp):
    user()
    code = sign_in(client, idp)[1]["code"]
    row = db.session.query(OidcLoginCode).one()
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.session.commit()
    assert exchange(client, code).status_code == 401
    assert db.session.query(OidcLoginCode).count() == 0


def test_only_a_hash_of_the_code_is_stored(client, idp):
    user()
    code = sign_in(client, idp)[1]["code"]
    assert code not in db.session.query(OidcLoginCode).one().code_hash


def test_an_unverified_email_is_never_linked(client, idp):
    user()
    target, params = sign_in(client, idp, {"email_verified": False})
    assert params == {"error": "email_unverified"}
    assert db.session.query(OidcIdentity).count() == 0
    target, params = sign_in(client, idp, {"email_verified": "true"})  # a string is not a yes
    assert params == {"error": "email_unverified"}


def test_a_missing_email_is_refused(client, idp):
    _, p, _ = begin(client)
    target, params = finish(client, p, idp, {"email": None})
    assert params == {"error": "no_email"}


def test_a_stranger_without_an_invite_gets_no_account(client, idp):
    target, params = sign_in(client, idp)
    assert params == {"error": "not_invited"}
    assert db.session.query(User).count() == 0


def test_an_invited_person_gets_an_account_with_their_role(client, idp, register):
    owner, _ = register("owner@example.com", "Owner")
    plot = client.post("/api/v1/allotments", json={"name": "Plot"}, headers=owner).json["id"]
    owner_id = db.session.query(User).filter_by(email="owner@example.com").one().id
    invite = make_invite(plot, "ann@example.com", "editor", owner_id)
    seen = []
    events.subscribe("*", lambda e: seen.append(e.type))

    target, params = sign_in(client, idp, query=f"?invite={invite}")
    assert "error" not in params
    ann = db.session.query(User).filter_by(email="ann@example.com").one()
    assert ann.password_hash is None and ann.display_name == "Ann"
    member = db.session.query(Membership).filter_by(user_id=ann.id, allotment_id=plot).one()
    assert member.role == "editor"
    assert exchange(client, params["code"]).status_code == 200
    assert {"user.registered", "member.added", "user.logged_in"} <= set(seen)


def test_an_invite_for_another_email_does_not_work(client, idp, register):
    owner, _ = register("owner@example.com", "Owner")
    plot = client.post("/api/v1/allotments", json={"name": "Plot"}, headers=owner).json["id"]
    invite = make_invite(plot, "someone.else@example.com", "editor", 1)
    target, params = sign_in(client, idp, query=f"?invite={invite}")
    assert params == {"error": "not_invited"}
    assert db.session.query(User).filter_by(email="ann@example.com").count() == 0


def test_a_forged_invite_does_not_work(client, idp):
    target, params = sign_in(client, idp, query="?invite=forged")
    assert params == {"error": "not_invited"}


def test_a_person_without_a_password_cannot_use_the_password_login(client, idp):
    ann = User(email="ann@example.com", display_name="Ann", password_hash=None)
    db.session.add(ann)
    db.session.commit()
    for password in ("", "password123", "x" * 20):
        resp = client.post(
            "/api/v1/auth/login", json={"email": "ann@example.com", "password": password}
        )
        assert resp.status_code in (401, 422)
    _, params = sign_in(client, idp)
    assert exchange(client, params["code"]).status_code == 200  # but single sign-on works


def test_a_tampered_or_foreign_state_is_refused(client, idp):
    _, params, _ = begin(client)
    target, got = finish(client, params, idp, state=params["state"] + "x")
    assert got == {"error": "invalid_state"}
    target, got = finish(client, params, idp, state="not-a-state")
    assert got == {"error": "invalid_state"}
    assert idp["token_requests"] == []  # never even asked the provider


def test_a_sign_in_must_finish_in_the_browser_that_started_it(client, idp):
    user()
    _, params, _ = begin(client)
    client.delete_cookie(BINDER, path="/api/v1/auth/oidc")  # someone else's browser has no cookie
    target, got = finish(client, params, idp)
    assert got == {"error": "invalid_state"}


def test_a_callback_cannot_be_replayed(client, idp):
    user()
    _, params, _ = begin(client)
    first = finish(client, params, idp)[1]
    assert "code" in first
    again = finish(client, params, idp)[1]
    assert again == {"error": "invalid_state"}  # the cookie was spent with the first one


def test_an_old_state_is_refused(client, idp, app):
    user()
    _, params, _ = begin(client)
    app.config["OIDC_STATE_TTL_SECONDS"] = -1
    assert finish(client, params, idp)[1] == {"error": "expired"}


def test_state_from_another_provider_is_refused(client, idp, app):
    user()
    app.config["OIDC_PROVIDERS"].append({**app.config["OIDC_PROVIDERS"][0], "id": "other"})
    _, params, _ = begin(client)
    idp["claims"] = {"nonce": params["nonce"]}
    resp = client.get(
        "/api/v1/auth/oidc/other/callback", query_string={"code": "c", "state": params["state"]}
    )
    assert parse_qs(urlparse(resp.headers["Location"]).query) == {"error": ["invalid_state"]}


@pytest.mark.parametrize(
    "claims",
    [
        {"nonce": "someone-elses"},
        {"aud": "another-client"},
        {"iss": "https://evil.test"},
        {"exp": 1},
        {"sub": None},
    ],
    ids=["nonce", "audience", "issuer", "expired", "no-subject"],
)
def test_a_bad_id_token_is_refused(client, idp, claims):
    user()
    _, params, _ = begin(client)
    target, got = finish(client, params, idp, claims)
    assert got == {"error": "invalid_id_token"}
    assert db.session.query(OidcIdentity).count() == 0


def test_an_id_token_signed_with_another_key_is_refused(client, idp):
    user()
    idp["key"] = OTHER_KEY
    _, params, _ = begin(client)
    assert finish(client, params, idp)[1] == {"error": "invalid_id_token"}


def test_a_provider_that_says_no_is_reported(client, idp):
    user()
    _, params, _ = begin(client)
    resp = client.get(
        "/api/v1/auth/oidc/idp/callback",
        query_string={"error": "access_denied", "state": params["state"]},
    )
    assert parse_qs(urlparse(resp.headers["Location"]).query) == {"error": ["denied"]}


def test_a_failed_token_exchange_is_reported(client, idp):
    user()
    _, params, _ = begin(client)
    # Replace the token endpoint with one that refuses (discovery is already cached).
    with responses.RequestsMock() as mock:
        mock.post(f"{ISSUER}/token", json={"error": "invalid_grant"}, status=400)
        resp = client.get(
            "/api/v1/auth/oidc/idp/callback", query_string={"code": "bad", "state": params["state"]}
        )
    assert parse_qs(urlparse(resp.headers["Location"]).query) == {
        "error": ["token_exchange_failed"]
    }


def test_an_unreachable_provider_sends_the_person_back_with_an_error(client, app):
    sso.clear_discovery_cache()
    with responses.RequestsMock() as mock:
        mock.get(f"{ISSUER}/.well-known/openid-configuration", status=503)
        resp = client.get("/api/v1/auth/oidc/idp/login")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/login?error=provider_unreachable"


def test_the_phone_app_is_sent_back_to_its_own_link(client, idp):
    user()
    back = "allotment://auth"
    _, params, _ = begin(client, f"?client=mobile&redirect={back}")
    target, got = finish(client, params, idp)
    assert target.startswith("allotment://auth?code=")
    assert exchange(client, got["code"]).status_code == 200


def test_the_phone_app_hears_about_failures_too(client, idp):
    _, params, _ = begin(client, "?client=mobile&redirect=allotment://auth")
    target, got = finish(client, params, idp)  # nobody has this email
    assert target == "allotment://auth?error=not_invited"


def test_the_phone_app_cannot_be_sent_anywhere_else(client):
    for back in ("https://evil.test/", "allotment://authevil", "javascript:alert(1)", ""):
        resp = client.get(
            "/api/v1/auth/oidc/idp/login", query_string={"client": "mobile", "redirect": back}
        )
        assert resp.status_code == 422, back
    ok = client.get(
        "/api/v1/auth/oidc/idp/login",
        query_string={"client": "mobile", "redirect": "allotment://auth/done"},
    )
    assert ok.status_code == 302


def test_a_failed_sign_in_is_recorded(client, idp):
    seen = []
    events.subscribe("user.login_failed", lambda e: seen.append(e.payload))
    sign_in(client, idp)
    assert seen == [{"provider": "idp", "reason": "not_invited"}]


class TestParsing:
    def test_a_generic_provider(self):
        raw = json.dumps(
            [{"id": "Auth", "issuer": "https://a.test/", "client_id": "i", "client_secret": "s"}]
        )
        [p] = parse_oidc_providers(raw)
        assert (p["id"], p["issuer"], p["name"], p["scopes"]) == (
            "auth",
            "https://a.test",
            "Auth",
            "openid email profile",
        )

    def test_presets(self):
        raw = json.dumps(
            [
                {"preset": "google", "client_id": "i", "client_secret": "s"},
                {
                    "preset": "microsoft",
                    "tenant": "organizations",
                    "client_id": "i",
                    "client_secret": "s",
                },
            ]
        )
        google, microsoft = parse_oidc_providers(raw)
        assert google["issuer"] == "https://accounts.google.com" and google["name"] == "Google"
        assert microsoft["issuer"] == "https://login.microsoftonline.com/organizations/v2.0"

    def test_incomplete_or_broken_entries_are_skipped_not_fatal(self):
        raw = json.dumps(
            [
                {"preset": "microsoft", "client_id": "i", "client_secret": "s"},  # no tenant
                {"id": "x", "issuer": "https://a.test", "client_id": "i"},  # no secret
                "nonsense",
                {"id": "ok", "issuer": "https://a.test", "client_id": "i", "client_secret": "s"},
                {"id": "ok", "issuer": "https://b.test", "client_id": "i", "client_secret": "s"},
            ]
        )
        assert [p["id"] for p in parse_oidc_providers(raw)] == ["ok"]
        assert parse_oidc_providers("{not json") == []
        assert parse_oidc_providers('{"a": 1}') == []
        assert parse_oidc_providers("") == [] and parse_oidc_providers(None) == []
