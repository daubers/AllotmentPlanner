import io

from allotment import events, sso
from allotment.extensions import db
from allotment.models import ActivityLog, Allotment, Media, Membership, User
from allotment.security import hash_password

from .helpers import make_jpeg

PASSWORD = "password123"


def make_plot(client, headers, name="Plot"):
    return client.post("/api/v1/allotments", json={"name": name}, headers=headers).json["id"]


def add_member(client, headers, plot_id, email, role="editor"):
    base = f"/api/v1/allotments/{plot_id}"
    resp = client.post(f"{base}/members", json={"email": email, "role": role}, headers=headers)
    assert resp.status_code == 201, resp.json


def upload(client, headers, plot_id):
    resp = client.post(
        f"/api/v1/allotments/{plot_id}/media",
        data={"file": (io.BytesIO(make_jpeg()), "p.jpg")},
        headers=headers,
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201, resp.json
    return resp.json


def delete_me(client, headers, **body):
    return client.delete("/api/v1/auth/me", json=body, headers=headers)


def stored_files(media_root):
    return sorted(p for p in media_root.rglob("*") if p.is_file())


def test_wrong_or_missing_password_is_refused_and_nothing_is_deleted(client, register):
    headers, _ = register()
    assert delete_me(client, headers, password="nope").status_code == 403
    assert delete_me(client, headers).status_code == 403
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200


def test_the_right_password_deletes_the_account_and_ends_its_tokens(client, register):
    headers, user = register()
    assert delete_me(client, headers, password=PASSWORD).status_code == 204
    assert db.session.get(User, user["id"]) is None
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    login = client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": PASSWORD})
    assert login.status_code == 401


def test_an_allotment_only_they_belong_to_goes_with_its_files(client, register, media_root):
    headers, _ = register()
    plot_id = make_plot(client, headers)
    upload(client, headers, plot_id)
    assert stored_files(media_root)
    assert delete_me(client, headers, password=PASSWORD).status_code == 204
    assert db.session.get(Allotment, plot_id) is None
    assert db.session.query(Media).count() == 0
    assert stored_files(media_root) == []


def test_the_only_owner_of_a_shared_allotment_must_hand_it_over_first(client, register):
    owner, _ = register("owner@example.com", "Owner")
    _, editor_user = register("editor@example.com", "Editor")
    plot_id = make_plot(client, owner, "Shared plot")
    add_member(client, owner, plot_id, "editor@example.com")
    resp = delete_me(client, owner, password=PASSWORD)
    assert resp.status_code == 409
    assert resp.json["errors"]["allotments"] == [{"id": plot_id, "name": "Shared plot"}]
    assert db.session.query(User).count() == 2 and db.session.get(Allotment, plot_id)

    # Hand it over, and the deletion goes through; the allotment stays with its new owner.
    promoted = client.patch(
        f"/api/v1/allotments/{plot_id}/members/{editor_user['id']}",
        json={"role": "owner"},
        headers=owner,
    )
    assert promoted.status_code == 200, promoted.json
    assert delete_me(client, owner, password=PASSWORD).status_code == 204
    assert db.session.get(Allotment, plot_id) is not None
    assert db.session.query(Membership).filter_by(allotment_id=plot_id).count() == 1


def test_a_co_owner_or_ordinary_member_just_leaves(client, register):
    owner, _ = register("owner@example.com", "Owner")
    editor, _ = register("editor@example.com", "Editor")
    plot_id = make_plot(client, owner)
    add_member(client, owner, plot_id, "editor@example.com")
    assert delete_me(client, editor, password=PASSWORD).status_code == 204
    assert db.session.get(Allotment, plot_id) is not None
    assert db.session.query(Membership).filter_by(allotment_id=plot_id).count() == 1


def test_what_they_added_to_a_shared_allotment_stays_unattributed(client, register, media_root):
    owner, _ = register("owner@example.com", "Owner")
    editor, editor_user = register("editor@example.com", "Editor")
    plot_id = make_plot(client, owner)
    add_member(client, owner, plot_id, "editor@example.com")
    media_id = upload(client, editor, plot_id)["id"]
    events.emit("allotment.updated", actor_id=editor_user["id"], allotment_id=plot_id)
    assert delete_me(client, editor, password=PASSWORD).status_code == 204
    assert db.session.get(Media, media_id).uploaded_by is None
    assert stored_files(media_root)
    assert all(
        row.actor_id is None
        for row in db.session.query(ActivityLog).filter_by(allotment_id=plot_id)
    )


def test_a_sso_only_account_needs_a_provider_confirmation(client, register):
    row = User(email="sso@example.com", display_name="Sso", password_hash=None)
    db.session.add(row)
    db.session.commit()
    token = client.post("/api/v1/auth/oidc/exchange", json={"code": sso.issue_code(row)}).json
    headers = {"Authorization": f"Bearer {token['access_token']}"}

    assert delete_me(client, headers).status_code == 403
    assert delete_me(client, headers, password="anything").status_code == 403
    # A login code is not a confirmation, nor is another user's confirmation.
    assert delete_me(client, headers, reauth_code=sso.issue_code(row)).status_code == 403
    other = User(email="o@example.com", display_name="O", password_hash=hash_password(PASSWORD))
    db.session.add(other)
    db.session.commit()
    assert (
        delete_me(client, headers, reauth_code=sso.issue_code(other, "reauth")).status_code == 403
    )
    assert db.session.get(User, row.id) is not None

    code = sso.issue_code(row, "reauth")
    assert delete_me(client, headers, reauth_code=code).status_code == 204
    assert db.session.get(User, row.id) is None


def test_a_confirmation_code_works_once(client):
    row = User(email="sso@example.com", display_name="Sso", password_hash=None)
    other = User(email="o@example.com", display_name="O", password_hash=None)
    db.session.add_all([row, other])
    db.session.commit()
    code = sso.issue_code(row, "reauth")
    assert sso.redeem_code(code, "reauth").id == row.id
    assert sso.redeem_code(code, "reauth") is None


def test_deletion_is_recorded_without_who(client, register):
    seen = []
    events.subscribe("user.deleted", lambda e: seen.append(e))
    headers, _ = register()
    make_plot(client, headers)
    delete_me(client, headers, password=PASSWORD)
    assert len(seen) == 1 and seen[0].payload == {"allotments_deleted": 1}
    assert seen[0].actor_id is None


# --- exporting their data ---------------------------------------------------------------------


def request_export(client, headers):
    resp = client.post("/api/v1/auth/me/export", headers=headers)
    assert resp.status_code == 202, resp.json
    return client.get(f"/api/v1/auth/me/export/{resp.json['id']}", headers=headers).json


def open_zip(client, export):
    import zipfile

    resp = client.get(export["url"])
    assert resp.status_code == 200 and resp.mimetype == "application/zip"
    assert "attachment" in resp.headers["Content-Disposition"]
    return zipfile.ZipFile(io.BytesIO(resp.data))


def test_an_export_holds_their_data_and_their_uploads_but_not_other_peoples(
    client, register, media_root
):
    import json

    owner, _ = register("owner@example.com", "Owner")
    editor, editor_user = register("editor@example.com", "Editor")
    plot_id = make_plot(client, owner, "Shared plot")
    add_member(client, owner, plot_id, "editor@example.com")
    mine = upload(client, editor, plot_id)
    theirs = upload(client, owner, plot_id)
    client.post(f"/api/v1/allotments/{plot_id}/tasks", json={"title": "Dig"}, headers=editor)
    client.post(f"/api/v1/allotments/{plot_id}/tasks", json={"title": "Not mine"}, headers=owner)

    export = request_export(client, editor)
    assert export["status"] == "ready" and export["url"] and export["size_bytes"] > 0
    zf = open_zip(client, export)
    data = json.loads(zf.read("data.json"))

    assert data["profile"]["email"] == "editor@example.com"
    assert "password_hash" not in json.dumps(data) and "$argon2" not in json.dumps(data)
    assert data["memberships"] == [
        {"allotment_id": plot_id, "allotment": "Shared plot", "role": "editor"}
    ]
    assert [t["title"] for t in data["content"]["tasks"]] == ["Dig"]
    [media_row] = data["content"]["media"]
    assert media_row["id"] == mine["id"] and theirs["id"] != mine["id"]
    assert zf.read(media_row["file"]) == stored_original(media_root, mine["id"])
    assert "storage_key" not in media_row
    assert sorted(zf.namelist()) == sorted(["data.json", media_row["file"]])


def stored_original(media_root, media_id):
    from allotment.models import Media

    return (media_root / db.session.get(Media, media_id).storage_key).read_bytes()


def test_the_download_link_needs_its_signature_and_dies_with_expiry(client, register):
    from datetime import UTC, datetime, timedelta

    from allotment.models import AccountExport

    headers, _ = register()
    export = request_export(client, headers)
    assert client.get(export["url"].split("?")[0]).status_code == 403
    assert client.get(export["url"].split("?")[0] + "?t=forged").status_code == 403
    row = db.session.get(AccountExport, export["id"])
    row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.session.commit()
    assert client.get(export["url"]).status_code == 410
    assert client.get(f"/api/v1/auth/me/export/{export['id']}", headers=headers).json == {
        **client.get(f"/api/v1/auth/me/export/{export['id']}", headers=headers).json,
        "status": "expired",
        "url": None,
    }


def test_nobody_else_can_see_an_export(client, register):
    headers, _ = register("a@example.com", "A")
    other, _ = register("b@example.com", "B")
    export = request_export(client, headers)
    assert client.get(f"/api/v1/auth/me/export/{export['id']}", headers=other).status_code == 404
    assert client.get(f"/api/v1/auth/me/export/{export['id']}").status_code == 401
    assert client.post("/api/v1/auth/me/export").status_code == 401


def test_pruning_removes_expired_exports_and_their_files(client, register, media_root):
    from datetime import UTC, datetime, timedelta

    from allotment.models import AccountExport
    from allotment.tasks import prune_account_exports

    headers, _ = register()
    export = request_export(client, headers)
    assert stored_files(media_root)
    assert prune_account_exports() == 0
    db.session.get(AccountExport, export["id"]).expires_at = datetime.now(UTC) - timedelta(hours=1)
    db.session.commit()
    assert prune_account_exports() == 1
    assert db.session.query(AccountExport).count() == 0
    assert stored_files(media_root) == []


def test_deleting_the_account_deletes_its_exports(client, register, media_root):
    headers, _ = register()
    request_export(client, headers)
    assert stored_files(media_root)
    assert delete_me(client, headers, password=PASSWORD).status_code == 204
    assert stored_files(media_root) == []
