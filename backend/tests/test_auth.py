import time

import pytest


def test_register_login_me_refresh(client):
    body = {"email": "New@Example.com", "display_name": "New", "password": "password123"}
    reg = client.post("/api/v1/auth/register", json=body)
    assert reg.status_code == 201
    assert "password" not in reg.json["user"]

    login = client.post(
        "/api/v1/auth/login", json={"email": "new@example.com", "password": "password123"}
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=headers).json["email"] == "new@example.com"

    refresh = client.post(
        "/api/v1/auth/refresh", headers={"Authorization": f"Bearer {login.json['refresh_token']}"}
    )
    assert refresh.status_code == 200 and refresh.json["access_token"]


def test_duplicate_email_conflicts(client, register):
    register()
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "display_name": "X", "password": "password123"},
    )
    assert resp.status_code == 409


def test_bad_credentials_rejected(client, register):
    register()
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "a@example.com", "password": "wrong"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "x"}
        ).status_code
        == 401
    )


def test_short_password_rejected(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "display_name": "A", "password": "short"},
    )
    assert resp.status_code == 422


def test_me_requires_token_and_access_token_cannot_refresh(client, register):
    assert client.get("/api/v1/auth/me").status_code == 401
    headers, _ = register()
    assert client.post("/api/v1/auth/refresh", headers=headers).status_code == 422


def test_openapi_documents_endpoints(client):
    paths = client.get("/api/openapi.json").json["paths"]
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/allotments/{allotment_id}/members" in paths


def _signup(client, email="b@example.com", **extra):
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": "B", "password": "password123", **extra},
    )


def test_auth_config_says_which_versions_the_server_is_and_works_with(client, app):
    app.config["APP_VERSION"] = "0.16.0"
    app.config["MIN_APP_VERSION"] = "1.5.0"
    body = client.get("/api/v1/auth/config").json
    assert body["server_version"] == "0.16.0"
    assert body["api_level"] == app.config["API_LEVEL"] >= 1
    assert body["min_app_version"] == "1.5.0"


def test_auth_config_defaults_to_open(client):
    body = client.get("/api/v1/auth/config").json
    assert (body["registration"], body["oidc"]) == ("open", [])


@pytest.fixture
def invite_only(app):
    app.config["REGISTRATION"] = "invite"


def test_invite_only_allows_first_account_then_closes(client, invite_only):
    body = client.get("/api/v1/auth/config").json
    assert (body["registration"], body["oidc"]) == ("invite", [])
    assert _signup(client, "first@example.com").status_code == 201
    resp = _signup(client, "second@example.com")
    assert resp.status_code == 403
    assert "invitation" in resp.json["message"]


def test_invite_lets_a_new_person_join_the_allotment(client, register, invite_only):
    headers, _ = register()
    allotment = client.post("/api/v1/allotments", json={"name": "Plot 4"}, headers=headers).json
    inv = client.post(
        f"/api/v1/allotments/{allotment['id']}/invites",
        json={"email": "Guest@Example.com", "role": "editor"},
        headers=headers,
    )
    assert inv.status_code == 201 and inv.json["email"] == "guest@example.com"

    resp = _signup(client, "guest@example.com", invite_code=inv.json["invite_code"])
    assert resp.status_code == 201
    guest = {"Authorization": f"Bearer {resp.json['access_token']}"}
    mine = client.get("/api/v1/allotments", headers=guest).json
    assert [(a["id"], a["role"]) for a in mine] == [(allotment["id"], "editor")]

    # used up: the address now has an account
    assert (
        _signup(client, "guest@example.com", invite_code=inv.json["invite_code"]).status_code == 409
    )


def test_invite_is_bound_to_its_email_and_must_be_genuine(client, register, invite_only):
    headers, _ = register()
    aid = client.post("/api/v1/allotments", json={"name": "P"}, headers=headers).json["id"]
    code = client.post(
        f"/api/v1/allotments/{aid}/invites", json={"email": "guest@example.com"}, headers=headers
    ).json["invite_code"]
    assert _signup(client, "other@example.com", invite_code=code).status_code == 403
    assert _signup(client, "guest@example.com", invite_code=code + "x").status_code == 403
    assert _signup(client, "guest@example.com", invite_code="nonsense").status_code == 403


def test_expired_invite_is_refused(client, register, invite_only, app):
    headers, _ = register()
    aid = client.post("/api/v1/allotments", json={"name": "P"}, headers=headers).json["id"]
    code = client.post(
        f"/api/v1/allotments/{aid}/invites", json={"email": "guest@example.com"}, headers=headers
    ).json["invite_code"]
    app.config["INVITE_TTL_DAYS"] = 0
    time.sleep(1.1)
    assert _signup(client, "guest@example.com", invite_code=code).status_code == 403


def test_only_owners_can_invite_and_existing_users_are_not_invited(client, register):
    owner, _ = register()
    aid = client.post("/api/v1/allotments", json={"name": "P"}, headers=owner).json["id"]
    viewer, _ = register("v@example.com", "V")
    client.post(f"/api/v1/allotments/{aid}/members", json={"email": "v@example.com"}, headers=owner)
    url = f"/api/v1/allotments/{aid}/invites"
    assert client.post(url, json={"email": "x@example.com"}, headers=viewer).status_code == 403
    assert client.post(url, json={"email": "v@example.com"}, headers=owner).status_code == 409


def test_invite_code_works_when_registration_is_open(client, register):
    headers, _ = register()
    aid = client.post("/api/v1/allotments", json={"name": "P"}, headers=headers).json["id"]
    code = client.post(
        f"/api/v1/allotments/{aid}/invites", json={"email": "g@example.com"}, headers=headers
    ).json["invite_code"]
    assert _signup(client, "g@example.com", invite_code=code).status_code == 201
