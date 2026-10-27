import pytest

from allotment import events


@pytest.fixture
def setup(client, register):
    owner, _ = register("owner@example.com", "Owner")
    editor, editor_user = register("editor@example.com", "Editor")
    viewer, viewer_user = register("viewer@example.com", "Viewer")
    stranger, _ = register("stranger@example.com", "Stranger")
    plot = client.post("/api/v1/allotments", json={"name": "Plot 12"}, headers=owner).json
    base = f"/api/v1/allotments/{plot['id']}"
    client.post(
        f"{base}/members", json={"email": "editor@example.com", "role": "editor"}, headers=owner
    )
    client.post(f"{base}/members", json={"email": "viewer@example.com"}, headers=owner)
    return {
        "base": base,
        "owner": owner,
        "editor": editor,
        "viewer": viewer,
        "stranger": stranger,
        "editor_id": editor_user["id"],
        "viewer_id": viewer_user["id"],
    }


def test_creator_becomes_owner(client, register):
    headers, _ = register()
    resp = client.post("/api/v1/allotments", json={"name": "Plot"}, headers=headers)
    assert resp.status_code == 201 and resp.json["role"] == "owner"
    assert [a["name"] for a in client.get("/api/v1/allotments", headers=headers).json] == ["Plot"]


def test_list_only_shows_own_allotments(client, setup):
    assert client.get("/api/v1/allotments", headers=setup["stranger"]).json == []
    assert len(client.get("/api/v1/allotments", headers=setup["viewer"]).json) == 1


def test_non_member_gets_404(client, setup):
    assert client.get(setup["base"], headers=setup["stranger"]).status_code == 404
    assert client.get("/api/v1/allotments/9999", headers=setup["owner"]).status_code == 404


def test_role_permissions(client, setup):
    base = setup["base"]
    for who in ("owner", "editor", "viewer"):
        assert client.get(base, headers=setup[who]).status_code == 200
    assert client.patch(base, json={"name": "New"}, headers=setup["owner"]).status_code == 200
    for who in ("editor", "viewer"):
        assert client.patch(base, json={"name": "Hack"}, headers=setup[who]).status_code == 403
        assert client.delete(base, headers=setup[who]).status_code == 403
        add = client.post(
            f"{base}/members", json={"email": "stranger@example.com"}, headers=setup[who]
        )
        assert add.status_code == 403


def test_add_member_errors(client, setup):
    base, owner = setup["base"], setup["owner"]
    assert (
        client.post(
            f"{base}/members", json={"email": "editor@example.com"}, headers=owner
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"{base}/members", json={"email": "ghost@example.com"}, headers=owner
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"{base}/members",
            json={"email": "stranger@example.com", "role": "admin"},
            headers=owner,
        ).status_code
        == 422
    )


def test_change_role_and_last_owner_protected(client, setup):
    base, owner = setup["base"], setup["owner"]
    promoted = client.patch(
        f"{base}/members/{setup['viewer_id']}", json={"role": "editor"}, headers=owner
    )
    assert promoted.json["role"] == "editor"
    owner_id = client.get("/api/v1/auth/me", headers=owner).json["id"]
    demote = client.patch(f"{base}/members/{owner_id}", json={"role": "viewer"}, headers=owner)
    assert demote.status_code == 409
    assert client.delete(f"{base}/members/{owner_id}", headers=owner).status_code == 409


def test_member_can_leave_but_not_remove_others(client, setup):
    base = setup["base"]
    assert (
        client.delete(f"{base}/members/{setup['editor_id']}", headers=setup["viewer"]).status_code
        == 403
    )
    assert (
        client.delete(f"{base}/members/{setup['viewer_id']}", headers=setup["viewer"]).status_code
        == 204
    )
    assert client.get(base, headers=setup["viewer"]).status_code == 404


def test_owner_can_remove_member_and_delete_allotment(client, setup):
    base, owner = setup["base"], setup["owner"]
    assert client.delete(f"{base}/members/{setup['editor_id']}", headers=owner).status_code == 204
    assert client.delete(base, headers=owner).status_code == 204
    assert client.get(base, headers=owner).status_code == 404


def test_domain_events_emitted(client, register):
    seen = []
    events.subscribe("*", lambda e: seen.append(e.type))
    headers, _ = register()
    client.post("/api/v1/allotments", json={"name": "Plot"}, headers=headers)
    assert {"user.registered", "allotment.created"} <= set(seen)
