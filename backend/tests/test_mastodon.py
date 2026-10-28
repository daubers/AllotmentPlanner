import io
import json
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs

import pytest
import responses

from allotment import events, mastodon_posts
from allotment.crypto import decrypt, encrypt
from allotment.extensions import db
from allotment.fediverse import normalise_instance_url
from allotment.models import MastodonAccount, MastodonPost
from allotment.tasks import mastodon_daily_digest, mastodon_sweep, send_mastodon_post

from .helpers import make_jpeg

INSTANCE = "https://social.example"
TOKEN = "tok-secret-1234567890"


@pytest.fixture
def plot(client, register):
    owner, _ = register("owner@example.com", "Owner")
    editor, _ = register("editor@example.com", "Editor")
    viewer, _ = register("viewer@example.com", "Viewer")
    stranger, _ = register("stranger@example.com", "Stranger")
    pid = client.post("/api/v1/allotments", json={"name": "Plot 12"}, headers=owner).json["id"]
    base = f"/api/v1/allotments/{pid}"
    client.post(
        f"{base}/members", json={"email": "editor@example.com", "role": "editor"}, headers=owner
    )
    client.post(f"{base}/members", json={"email": "viewer@example.com"}, headers=owner)
    return {
        "id": pid,
        "base": base,
        "mastodon": f"{base}/mastodon",
        "owner": owner,
        "editor": editor,
        "viewer": viewer,
        "stranger": stranger,
    }


def mock_verify(acct="plot", status=200):
    responses.add(
        responses.GET,
        f"{INSTANCE}/api/v1/accounts/verify_credentials",
        json={"acct": acct} if status == 200 else {"error": "The access token is invalid"},
        status=status,
    )


def connect(client, plot, **flags):
    mock_verify()
    body = {"instance_url": "social.example", "access_token": TOKEN, "enabled": True, **flags}
    resp = client.put(plot["mastodon"], json=body, headers=plot["owner"])
    assert resp.status_code == 200, resp.json
    return resp.json


def mock_status(url="https://social.example/@plot/1", status=200):
    responses.add(
        responses.POST,
        f"{INSTANCE}/api/v1/statuses",
        json={"id": "1", "url": url} if status == 200 else {"error": "boom"},
        status=status,
    )


def posts(client, plot, **query):
    return client.get(f"{plot['mastodon']}/posts", query_string=query, headers=plot["owner"]).json


def sent_bodies():
    return [c.request for c in responses.calls if c.request.url.endswith("/api/v1/statuses")]


def form(request) -> dict:
    """The status request's form fields, decoded: {'status': 'text', 'visibility': 'unlisted'}."""
    return {k: v if k.endswith("[]") else v[0] for k, v in parse_qs(request.body).items()}


# --- helpers -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Mastodon.Social/", "https://mastodon.social"),
        ("https://social.example", "https://social.example"),
        ("  social.example:8443 ", "https://social.example:8443"),
    ],
)
def test_normalise_instance_url(app, raw, expected):
    assert normalise_instance_url(raw) == expected


@pytest.mark.parametrize(
    "raw", ["", "ftp://x.example", "https://user:pw@x.example", "https://x.example/path?q=1"]
)
def test_normalise_rejects_bad_urls(app, raw):
    with pytest.raises(ValueError):
        normalise_instance_url(raw)


def test_token_encryption_round_trips_and_detects_a_changed_key(app):
    sealed = encrypt("abc")
    assert sealed != "abc"
    assert decrypt(sealed) == "abc"
    app.config["TOKEN_ENCRYPTION_KEY"] = "a-different-key"
    with pytest.raises(ValueError):
        decrypt(sealed)


# --- settings ------------------------------------------------------------------------------


def test_unconfigured_settings_and_roles(client, plot):
    resp = client.get(plot["mastodon"], headers=plot["editor"])
    assert resp.status_code == 200
    assert resp.json["configured"] is False and resp.json["enabled"] is False
    assert client.get(plot["mastodon"], headers=plot["viewer"]).status_code == 403
    assert client.get(plot["mastodon"], headers=plot["stranger"]).status_code == 404
    assert client.get(plot["mastodon"]).status_code == 401


@responses.activate
def test_connecting_verifies_the_token_and_stores_it_encrypted(client, plot, app):
    out = connect(client, plot, on_task_completed=True)
    assert out["configured"] and out["token_set"] and out["handle"] == "plot@social.example"
    assert out["instance_url"] == INSTANCE
    assert "access_token" not in json.dumps(out) and TOKEN not in json.dumps(out)
    assert client.get(plot["mastodon"], headers=plot["editor"]).json == out
    account = db.session.query(MastodonAccount).one()
    assert account.token_encrypted != TOKEN and decrypt(account.token_encrypted) == TOKEN
    assert responses.calls[0].request.headers["Authorization"] == f"Bearer {TOKEN}"


@responses.activate
def test_only_owner_can_change_settings(client, plot):
    body = {"instance_url": "social.example", "access_token": TOKEN}
    for who in ("editor", "viewer"):
        assert client.put(plot["mastodon"], json=body, headers=plot[who]).status_code == 403
    assert db.session.query(MastodonAccount).count() == 0


@responses.activate
def test_rejected_token_saves_nothing(client, plot):
    mock_verify(status=401)
    resp = client.put(
        plot["mastodon"],
        json={"instance_url": "social.example", "access_token": TOKEN},
        headers=plot["owner"],
    )
    assert resp.status_code == 422
    assert "rejected the access token" in resp.json["message"]
    assert db.session.query(MastodonAccount).count() == 0


def test_token_needed_to_connect_or_change_instance(client, plot):
    resp = client.put(
        plot["mastodon"], json={"instance_url": "social.example"}, headers=plot["owner"]
    )
    assert resp.status_code == 422 and "token is required" in resp.json["message"]


@responses.activate
def test_flags_can_change_without_resending_the_token(client, plot):
    connect(client, plot)
    resp = client.put(
        plot["mastodon"],
        json={"instance_url": INSTANCE, "on_photos": True, "visibility": "public", "enabled": True},
        headers=plot["owner"],
    )
    assert resp.status_code == 200
    assert resp.json["on_photos"] is True and resp.json["visibility"] == "public"
    assert len(responses.calls) == 1  # verified once, on connect
    resp = client.put(
        plot["mastodon"], json={"instance_url": "other.example"}, headers=plot["owner"]
    )
    assert resp.status_code == 422 and "new access token" in resp.json["message"]


def test_private_networks_and_plain_http_are_refused(client, plot, app):
    app.config["FEDIVERSE_ALLOW_PRIVATE_HOSTS"] = False
    for url, fragment in [
        ("https://10.0.0.5", "private network"),
        ("https://127.0.0.1", "private network"),
        ("https://[::1]", "private network"),
        ("http://social.example", "https"),
    ]:
        resp = client.put(
            plot["mastodon"],
            json={"instance_url": url, "access_token": TOKEN},
            headers=plot["owner"],
        )
        assert resp.status_code == 422, url
        assert fragment in resp.json["message"], url


@responses.activate
def test_disconnect_drops_queued_posts_but_keeps_history(client, plot):
    connect(client, plot, on_task_completed=True)
    pending = mastodon_posts.new_post(plot["id"], "task", "queued")
    pending.send_after = datetime.now(UTC) + timedelta(hours=1)
    sent = mastodon_posts.new_post(plot["id"], "task", "old")
    sent.status = "sent"
    db.session.commit()
    assert client.delete(plot["mastodon"], headers=plot["owner"]).status_code == 204
    statuses = {p["text"]: p["status"] for p in posts(client, plot)}
    assert statuses == {"queued": "skipped", "old": "sent"}
    assert client.get(plot["mastodon"], headers=plot["owner"]).json["configured"] is False
    assert client.delete(plot["mastodon"], headers=plot["owner"]).status_code == 404


# --- posting -------------------------------------------------------------------------------


def complete_task(client, plot, title="Sow carrots", feature=None):
    body = {"title": title}
    if feature:
        body["feature_id"] = feature
    task = client.post(f"{plot['base']}/tasks", json=body, headers=plot["editor"]).json
    client.post(f"{plot['base']}/tasks/{task['id']}/complete", headers=plot["editor"])


@responses.activate
def test_completed_task_is_posted_when_opted_in(client, plot):
    connect(client, plot, on_task_completed=True, visibility="unlisted")
    mock_status()
    bed = {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[-1, 51], [-1, 51.001], [-0.999, 51.001], [-0.999, 51], [-1, 51]]],
        },
        "properties": {"name": "Bed 1", "kind": "bed"},
    }
    fid = client.post(f"{plot['base']}/features", json=bed, headers=plot["editor"]).json["id"]
    complete_task(client, plot, feature=fid)
    [req] = sent_bodies()
    assert "Done: Sow carrots (Bed 1)" in form(req)["status"]
    assert form(req)["visibility"] == "unlisted"
    assert req.headers["Idempotency-Key"]
    [post] = posts(client, plot)
    assert post["status"] == "sent" and post["remote_url"] == "https://social.example/@plot/1"
    assert post["attempts"] == 1 and post["error"] is None


@responses.activate
def test_nothing_is_posted_unless_enabled_and_opted_in(client, plot):
    connect(client, plot, on_task_completed=False)
    complete_task(client, plot)
    connect_flags = {"instance_url": INSTANCE, "on_task_completed": True, "enabled": False}
    client.put(plot["mastodon"], json=connect_flags, headers=plot["owner"])
    complete_task(client, plot, "Weed")
    assert sent_bodies() == []
    assert posts(client, plot) == []


@responses.activate
def test_photo_is_posted_without_its_location_metadata(client, plot, media_root):
    connect(client, plot, on_photos=True)
    mock_status()
    responses.add(responses.POST, f"{INSTANCE}/api/v2/media", json={"id": "m1"}, status=200)
    original = make_jpeg(gps=(51.5, -0.12))
    assert b"Exif" in original
    resp = client.post(
        f"{plot['base']}/media",
        data={"file": (io.BytesIO(original), "p.jpg"), "caption": "Peas up!"},
        headers=plot["editor"],
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201, resp.json
    upload = next(c.request for c in responses.calls if c.request.url.endswith("/api/v2/media"))
    assert b"Exif" not in upload.body and b"GPS" not in upload.body
    assert b"Peas up!" in upload.body  # caption becomes the alt text
    [req] = sent_bodies()
    assert form(req)["media_ids[]"] == ["m1"]
    assert posts(client, plot)[0]["media_count"] == 1


@responses.activate
def test_slow_media_processing_is_polled_until_ready(client, plot, monkeypatch):
    monkeypatch.setattr("allotment.fediverse.time.sleep", lambda s: None)
    connect(client, plot, on_photos=True)
    mock_status()
    responses.add(responses.POST, f"{INSTANCE}/api/v2/media", json={"id": "m1"}, status=202)
    responses.add(responses.GET, f"{INSTANCE}/api/v1/media/m1", json={"id": "m1"}, status=206)
    responses.add(responses.GET, f"{INSTANCE}/api/v1/media/m1", json={"id": "m1"}, status=200)
    client.post(
        f"{plot['base']}/media",
        data={"file": (io.BytesIO(make_jpeg()), "p.jpg")},
        headers=plot["editor"],
        content_type="multipart/form-data",
    )
    assert posts(client, plot)[0]["status"] == "sent"


def test_a_burst_of_photos_becomes_posts_of_four(client, plot, app, monkeypatch):
    app.config["MASTODON_PHOTO_BATCH_SECONDS"] = 120
    queued = []
    monkeypatch.setattr(
        mastodon_posts, "enqueue", lambda post, countdown=0: queued.append(countdown)
    )
    with responses.RequestsMock(assert_all_requests_are_fired=False):
        connect_account = MastodonAccount(
            allotment_id=plot["id"],
            instance_url=INSTANCE,
            token_encrypted=encrypt(TOKEN),
            enabled=True,
            on_photos=True,
        )
        db.session.add(connect_account)
        db.session.commit()
        for media_id in range(1, 7):
            events.emit(
                "media.processed",
                allotment_id=plot["id"],
                subject={"media_id": media_id},
                payload={"kind": "photo"},
            )
        events.emit(  # videos are never posted
            "media.processed",
            allotment_id=plot["id"],
            subject={"media_id": 99},
            payload={"kind": "video"},
        )
    rows = db.session.query(MastodonPost).order_by(MastodonPost.id).all()
    assert [r.media_ids for r in rows] == [[1, 2, 3, 4], [5, 6]]
    assert "4 new photos" in rows[0].text and "2 new photos" in rows[1].text
    assert queued == [120, 120]  # one delayed send per post, not per photo


@responses.activate
def test_rejected_post_fails_with_the_reason_and_can_be_retried(client, plot):
    connect(client, plot, on_task_completed=True)
    responses.add(
        responses.POST,
        f"{INSTANCE}/api/v1/statuses",
        json={"error": "Validation failed"},
        status=422,
    )
    complete_task(client, plot)
    [post] = posts(client, plot)
    assert post["status"] == "failed" and "Validation failed" in post["error"]
    assert post["attempts"] == 1

    responses.replace(
        responses.POST, f"{INSTANCE}/api/v1/statuses", json={"id": "2", "url": "u"}, status=200
    )
    retry = client.post(f"{plot['mastodon']}/posts/{post['id']}/retry", headers=plot["owner"])
    assert retry.status_code == 202
    assert posts(client, plot)[0]["status"] == "sent"
    # only failed posts can be retried, and only by the owner
    again = client.post(f"{plot['mastodon']}/posts/{post['id']}/retry", headers=plot["owner"])
    assert again.status_code == 409
    assert (
        client.post(
            f"{plot['mastodon']}/posts/{post['id']}/retry", headers=plot["editor"]
        ).status_code
        == 403
    )


@responses.activate
def test_bad_token_at_post_time_is_permanent(client, plot):
    connect(client, plot, on_task_completed=True)
    responses.add(responses.POST, f"{INSTANCE}/api/v1/statuses", json={"error": "x"}, status=401)
    complete_task(client, plot)
    [post] = posts(client, plot)
    assert post["status"] == "failed" and "rejected the access token" in post["error"]


@responses.activate
def test_server_errors_back_off_then_give_up(client, plot):
    connect(client, plot, on_task_completed=True)
    mock_status(status=503)
    complete_task(client, plot)
    [post] = posts(client, plot)
    assert post["status"] == "pending" and post["attempts"] == 1
    assert "busy or down" in post["error"]
    assert datetime.fromisoformat(post["send_after"]) > datetime.now(UTC) + timedelta(seconds=20)

    row = db.session.get(MastodonPost, post["id"])
    for _ in range(10):  # each delivery is due; the 5th failure gives up
        row.send_after = datetime.now(UTC)
        db.session.commit()
        send_mastodon_post.apply(args=[row.id])
        db.session.refresh(row)
        if row.status == "failed":
            break
    assert row.status == "failed" and row.attempts == 5


@responses.activate
def test_unreachable_instance_is_transient(client, plot):
    connect(client, plot, on_task_completed=True)  # no status mock: connection refused
    complete_task(client, plot)
    [post] = posts(client, plot)
    assert post["status"] == "pending" and "Couldn't reach" in post["error"]


@responses.activate
def test_duplicate_delivery_posts_once(client, plot):
    connect(client, plot, on_task_completed=True)
    mock_status()
    complete_task(client, plot)
    [post] = posts(client, plot)
    assert send_mastodon_post.apply(args=[post["id"]]).result == "skipped"
    assert len(sent_bodies()) == 1


@responses.activate
def test_test_post_is_direct_and_needs_an_account(client, plot):
    assert client.post(f"{plot['mastodon']}/test", headers=plot["owner"]).status_code == 409
    connect(client, plot)
    mock_status()
    resp = client.post(f"{plot['mastodon']}/test", headers=plot["owner"])
    assert resp.status_code == 202 and resp.json["kind"] == "test"
    assert form(sent_bodies()[0])["visibility"] == "direct"
    assert client.post(f"{plot['mastodon']}/test", headers=plot["editor"]).status_code == 403


# --- digest and sweeper --------------------------------------------------------------------


@responses.activate
def test_daily_digest_posts_once_and_only_when_something_happened(client, plot):
    connect(client, plot, daily_digest=True)
    mock_status()
    assert mastodon_daily_digest.apply().result == 0  # quiet day: no post
    complete_task(client, plot, "A")
    complete_task(client, plot, "B")
    assert mastodon_daily_digest.apply().result == 1
    assert mastodon_daily_digest.apply().result == 0  # already sent today
    [req] = sent_bodies()
    assert "2 jobs done" in form(req)["status"]
    [post] = posts(client, plot)
    assert post["kind"] == "digest" and post["status"] == "sent"


@responses.activate
def test_digest_respects_the_opt_in(client, plot):
    connect(client, plot, daily_digest=False)
    complete_task(client, plot)
    assert mastodon_daily_digest.apply().result == 0


@responses.activate
def test_sweeper_requeues_lost_posts(client, plot):
    connect(client, plot)
    mock_status()
    lost = mastodon_posts.new_post(plot["id"], "task", "lost")
    lost.send_after = datetime.now(UTC) - timedelta(minutes=30)
    fresh = mastodon_posts.new_post(plot["id"], "task", "fresh")
    fresh.send_after = datetime.now(UTC) + timedelta(minutes=2)
    db.session.commit()
    assert mastodon_sweep.apply().result == 1
    assert {p["text"]: p["status"] for p in posts(client, plot)} == {
        "lost": "sent",
        "fresh": "pending",
    }


def test_post_list_filter_and_access(client, plot):
    mastodon_posts.new_post(plot["id"], "task", "a").status = "failed"
    mastodon_posts.new_post(plot["id"], "task", "b")
    db.session.commit()
    assert [p["text"] for p in posts(client, plot, status="failed")] == ["a"]
    assert client.get(f"{plot['mastodon']}/posts", headers=plot["viewer"]).status_code == 403
    assert client.get(f"{plot['mastodon']}/posts", headers=plot["stranger"]).status_code == 404
