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
