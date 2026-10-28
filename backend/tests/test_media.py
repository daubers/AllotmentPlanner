import io

import pytest
from PIL import Image

from allotment import events

from .helpers import HAVE_FFMPEG, make_jpeg, make_png, make_video

BED = {
    "type": "Polygon",
    "coordinates": [[[-1.0, 51.0], [-1.0, 51.001], [-0.999, 51.001], [-0.999, 51.0], [-1.0, 51.0]]],
}


@pytest.fixture
def plot(client, register):
    owner, _ = register("owner@example.com", "Owner")
    editor, _ = register("editor@example.com", "Editor")
    viewer, _ = register("viewer@example.com", "Viewer")
    stranger, _ = register("stranger@example.com", "Stranger")
    pid = client.post("/api/v1/allotments", json={"name": "Plot"}, headers=owner).json["id"]
    base = f"/api/v1/allotments/{pid}"
    client.post(
        f"{base}/members", json={"email": "editor@example.com", "role": "editor"}, headers=owner
    )
    client.post(f"{base}/members", json={"email": "viewer@example.com"}, headers=owner)
    bed = client.post(
        f"{base}/features",
        json={"type": "Feature", "geometry": BED, "properties": {"name": "Bed 1", "kind": "bed"}},
        headers=owner,
    ).json["id"]
    task = client.post(f"{base}/tasks", json={"title": "Dig"}, headers=owner).json["id"]
    return {
        "base": base,
        "url": f"{base}/media",
        "owner": owner,
        "editor": editor,
        "viewer": viewer,
        "stranger": stranger,
        "bed": bed,
        "task": task,
        "pid": pid,
    }


def upload(client, plot, data, name="photo.jpg", who="editor", **form):
    return client.post(
        plot["url"],
        data={"file": (io.BytesIO(data), name), **{k: str(v) for k, v in form.items()}},
        headers=plot[who],
        content_type="multipart/form-data",
    )


def stored_files(media_root):
    return sorted(p for p in media_root.rglob("*") if p.is_file())


def test_upload_photo_reads_exif_and_makes_thumbnail(client, plot):
    original = make_jpeg(size=(1000, 750), heading=90.0)
    resp = upload(
        client, plot, original, caption="First dig", feature_id=plot["bed"], task_id=plot["task"]
    )
    assert resp.status_code == 201, resp.json
    m = resp.json
    assert m["status"] == "ready" and m["kind"] == "photo" and m["error"] is None
    assert (m["width"], m["height"]) == (1000, 750)
    assert m["taken_at"].startswith("2026-10-27T14:03:05") and m["taken_at_source"] == "exif"
    assert m["lat"] == pytest.approx(51.5, abs=1e-4) and m["lng"] == pytest.approx(-0.12, abs=1e-4)
    assert m["heading"] == 90.0 and m["caption"] == "First dig"
    assert (m["feature_id"], m["task_id"]) == (plot["bed"], plot["task"])
    assert m["size_bytes"] == len(original) and m["filename"] == "photo.jpg"

    thumb = client.get(m["thumb_url"])
    assert thumb.status_code == 200 and thumb.mimetype == "image/jpeg"
    with Image.open(io.BytesIO(thumb.data)) as img:
        assert max(img.size) == 480
    full = client.get(m["url"])
    assert (
        full.status_code == 200
        and full.data == original
        and full.headers["Accept-Ranges"] == "bytes"
    )


def test_upload_without_exif_falls_back_to_upload_time(client, plot):
    m = upload(client, plot, make_png(), name="shot.png").json
    assert m["status"] == "ready" and m["taken_at_source"] == "upload"
    assert m["lat"] is None and m["heading"] is None
    assert m["content_type"] == "image/png"


def test_filename_is_sanitised(client, plot):
    m = upload(client, plot, make_png(), name="../../etc/pass wd.png").json
    assert "/" not in m["filename"] and ".." not in m["filename"]


@pytest.mark.parametrize(
    "data,status",
    [
        (b"", 422),
        (b"just some text, not media at all......", 415),
        (b"\0\0\0\x18ftypheic" + b"\0" * 40, 415),
    ],
)
def test_bad_uploads_rejected(client, plot, media_root, data, status):
    assert upload(client, plot, data).status_code == status
    assert stored_files(media_root) == []


def test_missing_file_and_oversize(client, plot):
    resp = client.post(
        plot["url"],
        data={"caption": "x"},
        headers=plot["editor"],
        content_type="multipart/form-data",
    )
    assert resp.status_code == 422
    assert upload(client, plot, make_jpeg() + b"\0" * (6 * 1024 * 1024)).status_code == 413


def test_corrupt_image_is_recorded_as_failed(client, plot):
    resp = upload(client, plot, b"\xff\xd8\xff" + b"garbage" * 50)
    assert resp.status_code == 201
    assert resp.json["status"] == "failed" and "Could not read image" in resp.json["error"]
    again = client.post(f"{plot['url']}/{resp.json['id']}/reprocess", headers=plot["editor"])
    assert again.status_code == 200 and again.json["status"] == "failed"


def test_refs_must_belong_to_allotment(client, plot, register):
    assert upload(client, plot, make_png(), feature_id=99999).status_code == 422
    assert upload(client, plot, make_png(), task_id=99999).status_code == 422


def test_roles_enforced(client, plot):
    m = upload(client, plot, make_png()).json
    one = f"{plot['url']}/{m['id']}"
    assert upload(client, plot, make_png(), who="viewer").status_code == 403
    assert upload(client, plot, make_png(), who="stranger").status_code == 404
    assert client.get(plot["url"], headers=plot["viewer"]).status_code == 200
    assert client.get(one, headers=plot["viewer"]).status_code == 200
    assert client.get(plot["url"], headers=plot["stranger"]).status_code == 404
    assert client.get(plot["url"]).status_code == 401
    assert client.patch(one, json={"caption": "x"}, headers=plot["viewer"]).status_code == 403
    assert client.delete(one, headers=plot["viewer"]).status_code == 403
    assert client.post(f"{one}/reprocess", headers=plot["viewer"]).status_code == 403


def test_signed_links(client, plot, app):
    a = upload(client, plot, make_png()).json
    b = upload(client, plot, make_png()).json
    path, token = a["url"].split("?t=")
    assert client.get(path).status_code == 403  # no token
    assert client.get(path + "?t=" + token[:-2] + "xx").status_code == 403  # tampered
    other = path.replace(f"/{a['id']}/", f"/{b['id']}/")
    assert client.get(other + "?t=" + token).status_code == 404  # token is for a different file
    app.config["MEDIA_URL_TTL_SECONDS"] = -1
    assert client.get(a["url"]).status_code == 403  # expired


def test_range_requests(client, plot):
    data = make_jpeg()
    m = upload(client, plot, data).json

    def get(rng):
        return client.get(m["url"], headers={"Range": rng})

    first = get("bytes=0-9")
    assert first.status_code == 206 and first.data == data[:10]
    assert first.headers["Content-Range"] == f"bytes 0-9/{len(data)}"
    assert get("bytes=5-").data == data[5:]
    assert get("bytes=-7").data == data[-7:]
    assert get(f"bytes=0-{len(data) * 10}").data == data  # end is clamped
    assert get(f"bytes={len(data) + 5}-").status_code == 416
    assert get("bytes=9-3").status_code == 416
    assert get("bytes=abc").status_code == 416
    assert get("bytes=-").status_code == 416


def test_list_filters_and_order(client, plot):
    early = upload(
        client, plot, make_jpeg(taken="2026:10:01 09:00:00"), feature_id=plot["bed"]
    ).json
    late = upload(client, plot, make_jpeg(taken="2026:10:20 09:00:00")).json
    png = upload(client, plot, make_png()).json  # taken "now"

    def ids(**q):
        return [
            m["id"] for m in client.get(plot["url"], query_string=q, headers=plot["viewer"]).json
        ]

    assert ids(order="asc")[:2] == [early["id"], late["id"]]
    assert ids()[0] == png["id"]  # newest first by default
    assert ids(feature_id=plot["bed"]) == [early["id"]]
    assert ids(taken_from="2026-10-15", taken_to="2026-10-25") == [late["id"]]
    assert ids(taken_to="2026-10-01") == [early["id"]]  # the whole of the end day counts
    assert ids(kind="video") == []
    assert ids(limit=1, offset=1, order="asc") == [late["id"]]
    assert (
        client.get(plot["url"], query_string={"kind": "audio"}, headers=plot["viewer"]).status_code
        == 422
    )


def test_patch_metadata_and_manual_placement(client, plot):
    m = upload(client, plot, make_png()).json
    one = f"{plot['url']}/{m['id']}"
    ok = client.patch(
        one,
        json={
            "caption": "Looking good",
            "feature_id": plot["bed"],
            "lat": 51.0005,
            "lng": -0.9995,
            "taken_at": "2026-09-01T10:00:00Z",
        },
        headers=plot["editor"],
    )
    assert ok.status_code == 200
    assert ok.json["caption"] == "Looking good" and ok.json["feature_id"] == plot["bed"]
    assert (ok.json["lat"], ok.json["lng"]) == (51.0005, -0.9995)
    assert (
        ok.json["taken_at"].startswith("2026-09-01T10:00:00")
        and ok.json["taken_at_source"] == "manual"
    )
    cleared = client.patch(
        one, json={"lat": None, "lng": None, "feature_id": None}, headers=plot["editor"]
    )
    assert cleared.json["lat"] is None and cleared.json["feature_id"] is None
    assert client.patch(one, json={"lat": 51.0}, headers=plot["editor"]).status_code == 422
    assert (
        client.patch(one, json={"lat": 51.0, "lng": None}, headers=plot["editor"]).status_code
        == 422
    )
    assert client.patch(one, json={"lat": 120, "lng": 0}, headers=plot["editor"]).status_code == 422
    assert client.patch(one, json={"feature_id": 99999}, headers=plot["editor"]).status_code == 422


def test_reprocessing_keeps_manual_time(client, plot):
    m = upload(client, plot, make_jpeg()).json
    one = f"{plot['url']}/{m['id']}"
    client.patch(one, json={"taken_at": "2025-01-01T00:00:00Z"}, headers=plot["editor"])
    again = client.post(f"{one}/reprocess", headers=plot["editor"]).json
    assert again["taken_at"].startswith("2025-01-01") and again["taken_at_source"] == "manual"


def test_delete_removes_row_and_files(client, plot, media_root):
    m = upload(client, plot, make_jpeg()).json
    assert len(stored_files(media_root)) == 2  # original + thumbnail
    assert client.delete(f"{plot['url']}/{m['id']}", headers=plot["editor"]).status_code == 204
    assert stored_files(media_root) == []
    assert client.get(f"{plot['url']}/{m['id']}", headers=plot["owner"]).status_code == 404


def test_deleting_allotment_removes_files(client, plot, media_root):
    upload(client, plot, make_jpeg())
    upload(client, plot, make_png())
    assert client.delete(plot["base"], headers=plot["owner"]).status_code == 204
    assert stored_files(media_root) == []


def test_deleting_feature_or_task_keeps_the_photo(client, plot):
    m = upload(client, plot, make_png(), feature_id=plot["bed"], task_id=plot["task"]).json
    client.delete(f"{plot['base']}/features/{plot['bed']}", headers=plot["owner"])
    client.delete(f"{plot['base']}/tasks/{plot['task']}", headers=plot["owner"])
    kept = client.get(f"{plot['url']}/{m['id']}", headers=plot["owner"]).json
    assert kept["feature_id"] is None and kept["task_id"] is None


def test_exif_orientation_is_applied_to_size_and_thumbnail(client, plot):
    m = upload(client, plot, make_jpeg(size=(600, 400), orientation=6)).json
    assert (m["width"], m["height"]) == (400, 600)
    with Image.open(io.BytesIO(client.get(m["thumb_url"]).data)) as img:
        assert img.size[1] > img.size[0]


def test_media_events_emitted(client, plot):
    seen = []
    events.subscribe("*", lambda e: seen.append((e.type, e.payload.get("has_gps"))))
    m = upload(client, plot, make_jpeg()).json
    client.patch(f"{plot['url']}/{m['id']}", json={"caption": "x"}, headers=plot["editor"])
    client.delete(f"{plot['url']}/{m['id']}", headers=plot["editor"])
    types = [t for t, _ in seen]
    assert {"media.uploaded", "media.processed", "media.updated", "media.deleted"} <= set(types)
    assert ("media.processed", True) in seen


@pytest.mark.skipif(not HAVE_FFMPEG, reason="ffmpeg not installed")
def test_upload_video(client, plot, tmp_path):
    data = make_video(tmp_path / "clip.mp4")
    resp = upload(client, plot, data, name="clip.mp4")
    assert resp.status_code == 201, resp.json
    m = resp.json
    assert m["kind"] == "video" and m["status"] == "ready" and m["content_type"] == "video/mp4"
    assert (m["width"], m["height"]) == (160, 120)
    assert m["duration_s"] == pytest.approx(2.0, abs=0.3)
    assert m["taken_at"].startswith("2026-10-27T14:03:05")
    assert (m["lat"], m["lng"]) == (51.5, -0.12)
    assert client.get(m["thumb_url"]).mimetype == "image/jpeg"
    part = client.get(m["url"], headers={"Range": "bytes=0-99"})
    assert part.status_code == 206 and part.data == data[:100]


# --- positions sent by the mobile app --------------------------------------------------------


def test_the_apps_own_position_beats_the_files_exif(client, plot):
    original = make_jpeg(size=(400, 300), heading=90.0)  # EXIF says 51.5, -0.12, facing 90
    m = upload(
        client,
        plot,
        original,
        lat=51.6174,
        lng=-1.1099,
        heading=200,
        taken_at="2026-10-28T09:30:00Z",
        capture_session="walk-1",
    ).json
    assert (m["lat"], m["lng"], m["heading"]) == (51.6174, -1.1099, 200.0)
    assert m["position_source"] == "device" and m["capture_session"] == "walk-1"
    assert m["taken_at"].startswith("2026-10-28T09:30:00") and m["taken_at_source"] == "device"


def test_exif_position_is_marked_as_coming_from_the_file(client, plot):
    m = upload(client, plot, make_jpeg(size=(400, 300))).json
    assert m["position_source"] == "exif"
    assert upload(client, plot, make_png(), name="b.png").json["position_source"] is None


def test_position_needs_both_halves_and_sane_numbers(client, plot):
    assert upload(client, plot, make_png(), lat=51.0).status_code == 422
    assert upload(client, plot, make_png(), lat=95, lng=0).status_code == 422
    assert upload(client, plot, make_png(), lat=51, lng=0, heading=400).status_code == 422


def test_resending_an_upload_returns_the_first_one(client, plot, media_root):
    before = len(stored_files(media_root))
    first = upload(client, plot, make_png(), client_id="abc123", capture_session="w")
    again = upload(client, plot, make_png(), name="again.png", client_id="abc123")
    assert first.status_code == again.status_code == 201
    assert again.json["id"] == first.json["id"]
    assert len(client.get(plot["url"], headers=plot["editor"]).json) == 1
    assert (
        len(stored_files(media_root)) - before <= 2
    )  # the first file and its thumbnail; none for the repeat
    other = upload(client, plot, make_png(), client_id="different")
    assert other.json["id"] != first.json["id"]


def test_media_can_be_listed_by_capture_session(client, plot):
    upload(client, plot, make_png(), capture_session="a")
    upload(client, plot, make_png(), capture_session="a")
    upload(client, plot, make_png(), capture_session="b")
    got = client.get(f"{plot['url']}?capture_session=a", headers=plot["viewer"]).json
    assert len(got) == 2 and {m["capture_session"] for m in got} == {"a"}


def test_setting_a_position_by_hand_is_recorded_as_manual(client, plot):
    mid = upload(client, plot, make_png()).json["id"]
    patched = client.patch(
        f"{plot['url']}/{mid}", json={"lat": 51.2, "lng": -1.2}, headers=plot["editor"]
    ).json
    assert patched["position_source"] == "manual"
    cleared = client.patch(
        f"{plot['url']}/{mid}", json={"lat": None, "lng": None}, headers=plot["editor"]
    ).json
    assert cleared["position_source"] is None
