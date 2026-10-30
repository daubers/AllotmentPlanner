import json
import os
from datetime import UTC, datetime

import pytest

from allotment import mapping_pipeline as pipeline
from allotment.extensions import db
from allotment.models import ActivityLog, MapJob, MapLayer, Media
from allotment.storage import get_storage
from allotment.tasks import run_map_job

from .helpers import HAVE_FFMPEG, make_jpeg, make_video

PNG = b"\x89PNG\r\n\x1a\nfake-tile"


@pytest.fixture
def queued(monkeypatch):
    """Capture jobs handed to the mapping queue instead of running the (heavy) pipeline."""
    calls = []
    monkeypatch.setattr(run_map_job, "apply_async", lambda args=None, **kw: calls.append(args[0]))
    return calls


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
    return {
        "id": pid,
        "base": base,
        "owner": owner,
        "editor": editor,
        "viewer": viewer,
        "stranger": stranger,
    }


def add_media(allotment_id, count, geotagged=True, kind="photo", status="ready"):
    ids = []
    for i in range(count):
        m = Media(
            allotment_id=allotment_id,
            kind=kind,
            filename=f"p{i}.jpg",
            content_type="image/jpeg",
            storage_key=f"allotments/{allotment_id}/x{i}.jpg",
            status=status,
            taken_at=datetime(2026, 10, 1 + i, tzinfo=UTC),
            lat=51.5 + i / 1e5 if geotagged else None,
            lng=-0.12 if geotagged else None,
        )
        db.session.add(m)
        db.session.flush()
        ids.append(m.id)
    db.session.commit()
    return ids


def create(client, plot, who="editor", **body):
    return client.post(f"{plot['base']}/map-jobs", json=body, headers=plot[who])


# --- creating jobs ---------------------------------------------------------------------------


def test_job_uses_every_ready_photo_by_default(client, plot, queued):
    ids = add_media(plot["id"], 6)
    add_media(plot["id"], 2, status="pending")  # still processing: left out
    resp = create(client, plot)
    assert resp.status_code == 202, resp.json
    job = resp.json
    assert job["status"] == "queued" and job["media_count"] == 6
    assert job["view"] == "oblique" and job["camera_height_m"] == 1.7
    assert job["name"].startswith("Map ")
    assert queued == [job["id"]]
    assert db.session.get(MapJob, job["id"]).media_ids == ids
    assert [
        j["id"] for j in client.get(f"{plot['base']}/map-jobs", headers=plot["editor"]).json
    ] == [job["id"]]


def test_job_options_and_explicit_selection(client, plot, queued):
    ids = add_media(plot["id"], 7)
    resp = create(
        client, plot, name=" Bed area ", media_ids=ids[:5], view="overhead", camera_height_m=25
    )
    assert resp.status_code == 202
    assert resp.json["name"] == "Bed area" and resp.json["view"] == "overhead"
    assert resp.json["media_count"] == 5 and resp.json["camera_height_m"] == 25


@pytest.mark.parametrize(
    "setup,body,fragment",
    [
        (lambda p: add_media(p, 4), {}, "at least 5"),
        (lambda p: add_media(p, 6, geotagged=False), {}, "need a location"),
        (lambda p: add_media(p, 6), {"view": "sideways"}, "view"),
        (lambda p: add_media(p, 6), {"camera_height_m": 0}, "camera_height_m"),
    ],
)
def test_job_validation(client, plot, queued, setup, body, fragment):
    setup(plot["id"])
    resp = create(client, plot, **body)
    assert resp.status_code == 422
    assert fragment in str(resp.json)
    assert queued == []


def test_job_rejects_media_that_isnt_ready_or_isnt_ours(client, plot, queued, register):
    ids = add_media(plot["id"], 6)
    other_owner, _ = register("other@example.com", "Other")
    other = client.post("/api/v1/allotments", json={"name": "Other"}, headers=other_owner).json[
        "id"
    ]
    foreign = add_media(other, 1)
    pending = add_media(plot["id"], 1, status="pending")
    assert create(client, plot, media_ids=[*ids[:4], foreign[0]]).status_code == 422
    assert create(client, plot, media_ids=[*ids[:4], pending[0]]).status_code == 422
    assert queued == []


def test_job_size_limit(client, plot, queued, app):
    add_media(plot["id"], 8)
    app.config["MAPPING_MAX_IMAGES"] = 7
    resp = create(client, plot)
    assert resp.status_code == 422 and "at most 7" in resp.json["message"]


def test_one_job_at_a_time_per_allotment(client, plot, queued):
    add_media(plot["id"], 6)
    assert create(client, plot).status_code == 202
    assert create(client, plot).status_code == 409


def test_job_roles(client, plot, queued):
    add_media(plot["id"], 6)
    assert create(client, plot, who="viewer").status_code == 403
    assert create(client, plot, who="stranger").status_code == 404
    assert client.get(f"{plot['base']}/map-jobs", headers=plot["viewer"]).status_code == 403
    assert create(client, plot, who="owner").status_code == 202


def test_cancel_and_delete(client, plot, queued):
    add_media(plot["id"], 6)
    jid = create(client, plot).json["id"]
    url = f"{plot['base']}/map-jobs/{jid}"
    assert client.delete(url, headers=plot["editor"]).status_code == 409  # active
    cancelled = client.post(f"{url}/cancel", headers=plot["editor"])
    assert cancelled.status_code == 202 and cancelled.json["status"] == "cancelled"
    assert client.post(f"{url}/cancel", headers=plot["editor"]).status_code == 409
    assert client.delete(url, headers=plot["editor"]).status_code == 204
    assert client.get(url, headers=plot["editor"]).status_code == 404


def test_cancelling_a_running_job_sets_the_flag(client, plot, queued):
    add_media(plot["id"], 6)
    jid = create(client, plot).json["id"]
    job = db.session.get(MapJob, jid)
    job.status = "running"
    db.session.commit()
    resp = client.post(f"{plot['base']}/map-jobs/{jid}/cancel", headers=plot["editor"])
    assert resp.json["status"] == "running" and resp.json["cancel_requested"] is True


def test_detail_includes_the_log_but_the_list_does_not(client, plot, queued):
    add_media(plot["id"], 6)
    jid = create(client, plot).json["id"]
    job = db.session.get(MapJob, jid)
    job.log = "== features\nextracting"
    db.session.commit()
    assert (
        client.get(f"{plot['base']}/map-jobs/{jid}", headers=plot["editor"])
        .json["log"]
        .startswith("== features")
    )
    assert client.get(f"{plot['base']}/map-jobs", headers=plot["editor"]).json[0]["log"] == ""


# --- layers and tiles ------------------------------------------------------------------------


def add_layer(app, plot, **kw):
    layer = MapLayer(
        allotment_id=plot["id"],
        name="Whole plot",
        west=-0.13,
        south=51.49,
        east=-0.11,
        north=51.51,
        min_zoom=17,
        max_zoom=21,
        tile_count=2,
        **kw,
    )
    db.session.add(layer)
    db.session.commit()
    os.makedirs(app.config["MEDIA_ROOT"], exist_ok=True)
    src = app.config["MEDIA_ROOT"] + "/tile-src.png"
    with open(src, "wb") as f:
        f.write(PNG)
    for z, x, y in ((18, 1, 2), (19, 3, 4)):
        get_storage().put(f"{layer.tile_prefix}/{z}/{x}/{y}.png", src, "image/png")
    return layer


def test_layers_are_listed_with_a_signed_tile_template(client, plot, app):
    layer = add_layer(app, plot)
    [out] = client.get(f"{plot['base']}/layers", headers=plot["viewer"]).json
    assert out["bounds"] == [-0.13, 51.49, -0.11, 51.51]
    assert (out["min_zoom"], out["max_zoom"], out["visible"], out["opacity"]) == (
        17,
        21,
        True,
        0.85,
    )
    assert out["tile_url"].startswith(f"/api/v1/layers/{layer.id}/tiles/{{z}}/{{x}}/{{y}}.png?t=")
    assert client.get(f"{plot['base']}/layers", headers=plot["stranger"]).status_code == 404


def test_tiles_are_served_with_a_token_and_missing_ones_are_blank(client, plot, app):
    layer = add_layer(app, plot)
    template = client.get(f"{plot['base']}/layers", headers=plot["viewer"]).json[0]["tile_url"]
    token = template.split("?t=")[1]
    ok = client.get(f"/api/v1/layers/{layer.id}/tiles/18/1/2.png?t={token}")  # no bearer header
    assert ok.status_code == 200 and ok.data == PNG and ok.mimetype == "image/png"
    assert "max-age=3600" in ok.headers["Cache-Control"]
    blank = client.get(f"/api/v1/layers/{layer.id}/tiles/18/9/9.png?t={token}")
    assert blank.status_code == 200 and blank.data[:8] == PNG[:8] and blank.data != PNG
    assert client.get(f"/api/v1/layers/{layer.id}/tiles/18/1/2.png").status_code == 403
    assert client.get(f"/api/v1/layers/{layer.id}/tiles/18/1/2.png?t=garbage").status_code == 403
    other = add_layer(app, plot)
    assert client.get(f"/api/v1/layers/{other.id}/tiles/18/1/2.png?t={token}").status_code == 404


def test_tile_token_expires(client, plot, app):
    layer = add_layer(app, plot)
    token = (
        client.get(f"{plot['base']}/layers", headers=plot["viewer"])
        .json[0]["tile_url"]
        .split("?t=")[1]
    )
    app.config["MAPPING_TILE_TOKEN_TTL_SECONDS"] = -1
    assert client.get(f"/api/v1/layers/{layer.id}/tiles/18/1/2.png?t={token}").status_code == 403


def test_layer_settings_and_roles(client, plot, app):
    layer = add_layer(app, plot)
    url = f"{plot['base']}/layers/{layer.id}"
    resp = client.patch(
        url, json={"opacity": 0.4, "visible": False, "name": "Autumn"}, headers=plot["editor"]
    )
    assert resp.status_code == 200
    assert (resp.json["opacity"], resp.json["visible"], resp.json["name"]) == (0.4, False, "Autumn")
    assert client.patch(url, json={"opacity": 1.5}, headers=plot["editor"]).status_code == 422
    assert client.patch(url, json={"name": ""}, headers=plot["editor"]).status_code == 422
    assert client.patch(url, json={"visible": True}, headers=plot["viewer"]).status_code == 403
    assert client.delete(url, headers=plot["viewer"]).status_code == 403


def test_deleting_a_layer_removes_its_tiles(client, plot, app):
    layer = add_layer(app, plot)
    prefix = layer.tile_prefix
    assert (
        client.delete(f"{plot['base']}/layers/{layer.id}", headers=plot["editor"]).status_code
        == 204
    )
    assert get_storage().get_bytes(f"{prefix}/18/1/2.png") is None
    assert db.session.get(MapLayer, layer.id) is None
    assert (
        client.delete(f"{plot['base']}/layers/{layer.id}", headers=plot["editor"]).status_code
        == 404
    )


def test_deleting_the_allotment_removes_layer_tiles(client, plot, app):
    layer = add_layer(app, plot)
    prefix = layer.tile_prefix
    assert client.delete(plot["base"], headers=plot["owner"]).status_code == 204
    assert get_storage().get_bytes(f"{prefix}/18/1/2.png") is None


# --- the task --------------------------------------------------------------------------------


@pytest.fixture
def job(plot, monkeypatch, tmp_path):
    monkeypatch.setenv("MAPPING_WORK_DIR", str(tmp_path / "work"))
    (tmp_path / "work").mkdir()
    ids = add_media(plot["id"], 6)
    j = MapJob(allotment_id=plot["id"], name="Test map", media_ids=ids)
    db.session.add(j)
    db.session.commit()
    return j


def test_successful_job_creates_a_layer_and_counts_as_a_map_edit(
    client, plot, job, monkeypatch, tmp_path
):
    def fake_process(j, work):
        assert work.exists()
        layer = MapLayer(
            allotment_id=j.allotment_id, job_id=j.id, name=j.name, west=0, south=0, east=1, north=1,
            min_zoom=18, max_zoom=21, tile_count=9,
        )  # fmt: skip
        db.session.add(layer)
        db.session.flush()
        return layer

    monkeypatch.setattr(pipeline, "process", fake_process)
    assert run_map_job.apply(args=[job.id]).result == "ready"
    db.session.refresh(job)
    assert job.status == "ready" and job.started_at and job.finished_at and job.error is None
    layer = db.session.query(MapLayer).one()
    listed = client.get(f"{plot['base']}/map-jobs", headers=plot["editor"]).json[0]
    assert listed["layer_id"] == layer.id
    assert db.session.query(ActivityLog).filter_by(type="layer.created").count() == 1
    overview = client.get(f"{plot['base']}/overview", headers=plot["owner"]).json
    assert overview["totals"]["map_edits"] == 1
    assert list((tmp_path / "work").iterdir()) == []  # the scratch folder is always removed


@pytest.mark.parametrize(
    "error,status,message",
    [
        (pipeline.JobFailed("Only 2 have a location"), "failed", "Only 2 have a location"),
        (pipeline.JobCancelled(), "cancelled", None),
        (RuntimeError("boom"), "failed", "Unexpected error: RuntimeError"),
    ],
)
def test_job_outcomes(plot, job, monkeypatch, error, status, message):
    def fake_process(j, work):
        raise error

    monkeypatch.setattr(pipeline, "process", fake_process)
    assert run_map_job.apply(args=[job.id]).result == status
    db.session.refresh(job)
    assert job.status == status and job.error == message and job.finished_at
    assert db.session.query(MapLayer).count() == 0


def test_job_cancelled_before_it_starts_never_runs(plot, job, monkeypatch):
    monkeypatch.setattr(pipeline, "process", lambda *a: pytest.fail("must not run"))
    job.cancel_requested = True
    db.session.commit()
    assert run_map_job.apply(args=[job.id]).result == "cancelled"


def test_only_queued_jobs_run(plot, job, monkeypatch):
    monkeypatch.setattr(pipeline, "process", lambda *a: pytest.fail("must not run"))
    job.status = "ready"
    db.session.commit()
    assert run_map_job.apply(args=[job.id]).result == "skipped"
    assert run_map_job.apply(args=[99999]).result == "skipped"


# --- preparing the OpenSfM dataset (runs for real; needs no OpenSfM) -------------------------


def store_photos(allotment_id, count, geotagged=True):
    """Media rows backed by real JPEG files in storage."""
    ids = add_media(allotment_id, count, geotagged=geotagged)
    for media_id in ids:
        media = db.session.get(Media, media_id)
        path = os.path.join(os.environ["MAPPING_WORK_DIR"], f"src{media_id}.jpg")
        with open(path, "wb") as f:
            f.write(make_jpeg())
        get_storage().put(media.storage_key, path, "image/jpeg")
    return ids


def test_dataset_has_images_gps_overrides_and_config(plot, job, tmp_path):
    ids = store_photos(plot["id"], 6)
    job.media_ids, job.view, job.camera_height_m = ids, "overhead", 12.0
    db.session.commit()
    work = tmp_path / "ds"
    assert pipeline.prepare_dataset(job, work) == 6
    assert sorted(p.name for p in (work / "images").iterdir()) == sorted(f"m{i}.jpg" for i in ids)
    overrides = json.loads((work / "exif_overrides.json").read_text())
    gps = overrides[f"m{ids[0]}.jpg"]["gps"]
    assert (gps["latitude"], gps["longitude"]) == (51.5, -0.12)
    assert gps["altitude"] == 12.0 and gps["dop"] == pipeline.GPS_ACCURACY_M
    config = (work / "config.yaml").read_text()
    assert "align_orientation_prior: vertical" in config and "use_altitude_tag: true" in config


def test_dataset_handheld_photos_assume_a_level_camera(plot, job, tmp_path):
    job.media_ids = store_photos(plot["id"], 5)
    db.session.commit()
    pipeline.prepare_dataset(job, tmp_path / "ds")
    assert "align_orientation_prior: horizontal" in (tmp_path / "ds" / "config.yaml").read_text()


def test_dataset_needs_enough_images_and_locations(plot, job, tmp_path):
    job.media_ids = store_photos(plot["id"], 4)
    db.session.commit()
    with pytest.raises(pipeline.JobFailed, match="at least 5"):
        pipeline.prepare_dataset(job, tmp_path / "a")
    job.media_ids = store_photos(plot["id"], 6, geotagged=False)
    db.session.commit()
    with pytest.raises(pipeline.JobFailed, match="Only 0 of the photos have a location"):
        pipeline.prepare_dataset(job, tmp_path / "b")


def test_dataset_ignores_media_from_elsewhere_or_not_ready(plot, job, tmp_path, register, client):
    mine = store_photos(plot["id"], 5)
    owner, _ = register("other@example.com", "Other")
    other = client.post("/api/v1/allotments", json={"name": "Other"}, headers=owner).json["id"]
    foreign = add_media(other, 1)
    pending = add_media(plot["id"], 1, status="pending")
    job.media_ids = [*mine, *foreign, *pending]
    db.session.commit()
    assert pipeline.prepare_dataset(job, tmp_path / "ds") == 5


def test_a_few_geotagged_photos_are_enough_for_overlapping_untagged_ones(plot, job, tmp_path):
    job.media_ids = store_photos(plot["id"], 3) + store_photos(plot["id"], 4, geotagged=False)
    db.session.commit()
    work = tmp_path / "ds"
    assert pipeline.prepare_dataset(job, work) == 7
    assert len(json.loads((work / "exif_overrides.json").read_text())) == 3


def test_a_job_can_be_built_from_a_capture_session(client, plot, queued):
    ids = add_media(plot["id"], 6)
    other = add_media(plot["id"], 3)
    db.session.query(Media).filter(Media.id.in_(ids)).update({"capture_session": "walk"})
    db.session.query(Media).filter(Media.id.in_(other)).update({"capture_session": "later"})
    db.session.commit()
    resp = create(client, plot, capture_session="walk")
    assert resp.status_code == 202, resp.json
    assert db.session.get(MapJob, resp.json["id"]).media_ids == ids


def test_capture_session_and_media_ids_do_not_mix_and_must_exist(client, plot, queued):
    ids = add_media(plot["id"], 6)
    assert create(client, plot, capture_session="x", media_ids=ids).status_code == 422
    assert create(client, plot, capture_session="nothing-here").status_code == 422


# --- videos --------------------------------------------------------------------------------


def add_video(allotment_id, seconds, located=False, storage_key=None):
    m = Media(
        allotment_id=allotment_id,
        kind="video",
        filename="walk.mp4",
        content_type="video/mp4",
        storage_key=storage_key or f"allotments/{allotment_id}/walk.mp4",
        status="ready",
        duration_s=seconds,
        taken_at=datetime(2026, 10, 20, tzinfo=UTC),
        lat=51.5 if located else None,
        lng=-0.12 if located else None,
    )
    db.session.add(m)
    db.session.commit()
    return m.id


def test_videos_are_included_by_default_and_count_as_their_frames(client, plot, queued):
    add_media(plot["id"], 3)
    add_video(plot["id"], 10)  # about 10 frames
    resp = create(client, plot)
    assert resp.status_code == 202, resp.json
    assert resp.json["media_count"] == 4  # three photos and the video


def test_a_video_alone_cannot_place_a_map(client, plot, queued):
    add_video(plot["id"], 60, located=True)  # plenty of frames, and even a location
    resp = create(client, plot)
    assert resp.status_code == 422
    assert "0 have one" in resp.json["message"] and "only one location" in resp.json["message"]


def test_a_videos_location_does_not_count_towards_placing_the_map(client, plot, queued):
    add_media(plot["id"], 2)  # two located photos...
    add_media(plot["id"], 3, geotagged=False)
    add_video(plot["id"], 30, located=True)  # ...and a located video: still only two
    assert create(client, plot).status_code == 422


def test_a_very_short_video_does_not_make_up_the_numbers(client, plot, queued):
    add_media(plot["id"], 3)
    add_video(plot["id"], 1)  # one frame: 3 + 1 < 5
    resp = create(client, plot)
    assert resp.status_code == 422 and "at least 5" in resp.json["message"]


def test_video_frames_count_against_the_image_limit(client, plot, queued, app):
    add_media(plot["id"], 3)
    for _ in range(3):
        add_video(plot["id"], 600)  # each capped at 60 frames
    resp = create(client, plot)
    assert resp.status_code == 422 and "about 183 images" in resp.json["message"]
    app.config["MAPPING_MAX_IMAGES"] = 200
    assert create(client, plot).status_code == 202


# --- sampling arithmetic and frame choice ----------------------------------------------------


def test_frame_rate_covers_long_videos_end_to_end():
    from allotment.mapping_video import estimated_frames, video_frame_rate

    assert video_frame_rate(4.0, 1.0, 60) == 1.0
    assert video_frame_rate(120.0, 1.0, 60) == 0.5  # 60 frames spread over two minutes
    assert video_frame_rate(None, 1.0, 60) == 1.0
    assert estimated_frames(4.0, 1.0, 60) == 4
    assert estimated_frames(120.0, 1.0, 60) == 60
    assert estimated_frames(None, 1.0, 60) == 60
    assert estimated_frames(0.2, 1.0, 60) == 1


def _noise_jpeg(path, blur=0):
    import numpy as np
    from PIL import Image, ImageFilter

    rng = np.random.default_rng(3)
    img = Image.fromarray((rng.random((240, 320, 3)) * 255).astype("uint8"))
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    img.save(path, "JPEG", quality=95)
    return path


def test_sharpness_ranks_blurred_frames_lower(tmp_path):
    sharp = pipeline.sharpness(_noise_jpeg(tmp_path / "a.jpg"))
    soft = pipeline.sharpness(_noise_jpeg(tmp_path / "b.jpg", blur=2))
    very_soft = pipeline.sharpness(_noise_jpeg(tmp_path / "c.jpg", blur=6))
    assert sharp > soft > very_soft


def test_a_frame_that_repeats_the_last_is_a_near_duplicate(tmp_path):
    a = _noise_jpeg(tmp_path / "a.jpg")
    same = _noise_jpeg(tmp_path / "b.jpg")
    other = tmp_path / "c.jpg"
    from PIL import Image

    Image.new("RGB", (320, 240), (200, 30, 30)).save(other)
    assert pipeline.near_duplicate(a, same)
    assert not pipeline.near_duplicate(a, other)


def _fix(lat, lng, taken, source="exif"):
    return (lat, lng, datetime(2026, 10, 27, 16, 52, taken, tzinfo=UTC), source)


def test_photos_that_never_changed_place_are_not_trusted(job):
    stuck = {f"m{i}.jpg": _fix(51.61743, -1.10998, 0) for i in range(5)}
    stuck["m4.jpg"] = (51.61743, -1.10998, datetime(2026, 10, 27, 16, 54, 30, tzinfo=UTC), "exif")
    assert pipeline.photo_locations(stuck, job) == {}
    assert "looks stuck" in job.log


def test_positions_read_by_the_app_are_never_called_stuck(job):
    same_spot = {f"m{i}.jpg": _fix(51.61743, -1.10998, 0, "device") for i in range(5)}
    same_spot["m4.jpg"] = (
        51.61743,
        -1.10998,
        datetime(2026, 10, 27, 16, 54, 30, tzinfo=UTC),
        "device",
    )
    assert len(pipeline.photo_locations(same_spot, job)) == 5
    mixed = {
        **{f"e{i}.jpg": _fix(51.0, -1.0, 0) for i in range(5)},
        "d.jpg": _fix(51.5, -1.5, 0, "device"),
    }
    mixed["e4.jpg"] = (51.0, -1.0, datetime(2026, 10, 27, 16, 55, tzinfo=UTC), "exif")
    assert set(pipeline.photo_locations(mixed, job)) == {
        "d.jpg"
    }  # the stuck EXIF ones go, the app's stay


def test_photos_in_different_places_or_taken_together_are_trusted(job):
    moving = {f"m{i}.jpg": _fix(51.6174 + i * 1e-4, -1.1099, 0) for i in range(5)}
    assert len(pipeline.photo_locations(moving, job)) == 5
    burst = {f"m{i}.jpg": _fix(51.6174, -1.1099, i) for i in range(5)}  # one place, seconds apart
    assert len(pipeline.photo_locations(burst, job)) == 5


def test_opensfm_config_links_video_frames_to_photos(job):
    plain = pipeline.opensfm_config(job)
    assert "matching_bow_neighbors" not in plain and "matching_order_neighbors" not in plain
    with_video = pipeline.opensfm_config(job, has_frames=True)
    assert with_video["matching_order_neighbors"] == 6
    assert with_video["matching_bow_neighbors"] == 10 and with_video["matching_bow_other_cameras"]
    assert with_video["align_orientation_prior"] == "horizontal"


@pytest.mark.skipif(not HAVE_FFMPEG, reason="ffmpeg not installed")
def test_dataset_from_photos_and_a_real_video(plot, job, tmp_path):
    photos = store_photos(plot["id"], 3)
    clip = tmp_path / "clip.mp4"
    make_video(clip, seconds=6)
    key = f"allotments/{plot['id']}/walk.mp4"
    get_storage().put(key, str(clip), "video/mp4")
    video = add_video(plot["id"], 6.0, located=True, storage_key=key)
    job.media_ids = [*photos, video]
    db.session.commit()

    work = tmp_path / "ds"
    assert pipeline.prepare_dataset(job, work) == 3 + 6
    frames = sorted(p.name for p in (work / "images").iterdir() if p.name.startswith("v"))
    assert frames == [f"v{video}_{n:04d}.jpg" for n in range(1, 7)]
    overrides = json.loads((work / "exif_overrides.json").read_text())
    assert all(
        "gps" not in overrides[f] and overrides[f]["camera"] == f"video {video}" for f in frames
    )
    assert sum("gps" in v for v in overrides.values()) == 3  # only the photos are located
    config = (work / "config.yaml").read_text()
    assert "matching_bow_neighbors: 10" in config and "matching_order_neighbors: 6" in config


# --- a plot boundary from a GPX trace -------------------------------------------------------


def square_polygon(side_m=20.0, lat=51.5, lon=-0.12):
    dlat = side_m / 111_320
    dlon = side_m / (111_320 * 0.6225)
    ring = [[lon, lat], [lon + dlon, lat], [lon + dlon, lat + dlat], [lon, lat + dlat], [lon, lat]]
    return {"type": "Polygon", "coordinates": [ring]}


def gpx_file(side_m=20.0, closed=True, keep=None):
    import io

    dlat = side_m / 111_320
    dlon = side_m / (111_320 * 0.6225)
    corners = [(0, 0), (1, 0), (1, 1), (0, 1)]
    pts = []
    for (ax, ay), (bx, by) in zip(corners, corners[1:] + corners[:1], strict=True):
        for i in range(8):
            t = i / 8
            pts.append((51.5 + (ay + (by - ay) * t) * dlat, -0.12 + (ax + (bx - ax) * t) * dlon))
    if closed:
        pts.append((51.5, -0.12))
    if keep is not None:
        pts = pts[:keep]
    body = "".join(f'<trkpt lat="{a:.7f}" lon="{b:.7f}"/>' for a, b in pts)
    xml = f'<gpx xmlns="http://www.topografix.com/GPX/1/1"><trk><trkseg>{body}</trkseg></trk></gpx>'
    return io.BytesIO(xml.encode())


def read_gpx(client, plot, data, who="editor", name="plot.gpx"):
    return client.post(
        f"{plot['base']}/boundary-from-gpx",
        data={"file": (data, name)},
        headers=plot[who],
        content_type="multipart/form-data",
    )


def test_a_gpx_walk_becomes_an_outline_to_check(client, plot):
    resp = read_gpx(client, plot, gpx_file())
    assert resp.status_code == 200, resp.json
    out = resp.json
    assert out["polygon"]["type"] == "Polygon"
    assert out["area_m2"] == pytest.approx(400, rel=0.05) and out["perimeter_m"] == pytest.approx(
        80, rel=0.05
    )
    assert out["points_in"] == 33 and out["points_out"] < out["points_in"] and out["warnings"] == []


@pytest.mark.parametrize(
    ("data", "fragment"),
    [
        ("not xml", "readable"),
        ("<html/>", "not a GPX"),
        ("<gpx/>", "no track"),
    ],
)
def test_a_file_that_is_not_a_usable_trace_says_why(client, plot, data, fragment):
    import io

    resp = read_gpx(client, plot, io.BytesIO(data.encode()))
    assert resp.status_code == 422 and fragment in resp.json["message"]


def test_a_walk_that_does_not_come_back_is_refused(client, plot):
    resp = read_gpx(client, plot, gpx_file(side_m=80, closed=False, keep=14))
    assert resp.status_code == 422 and "from where it started" in resp.json["message"]


def test_the_gpx_endpoint_needs_a_file_and_an_editor(client, plot):
    assert read_gpx(client, plot, gpx_file(), who="viewer").status_code == 403
    assert read_gpx(client, plot, gpx_file(), who="stranger").status_code == 404
    no_file = client.post(
        f"{plot['base']}/boundary-from-gpx",
        data={},
        headers=plot["editor"],
        content_type="multipart/form-data",
    )
    assert no_file.status_code == 422


def test_a_job_can_carry_a_boundary_and_it_is_kept(client, plot, queued):
    add_media(plot["id"], 6)
    boundary = square_polygon()
    resp = create(client, plot, boundary=boundary)
    assert resp.status_code == 202, resp.json
    assert resp.json["boundary"]["type"] == "Polygon"
    stored = db.session.get(MapJob, resp.json["id"]).boundary
    assert stored == boundary
    detail = client.get(f"{plot['base']}/map-jobs/{resp.json['id']}", headers=plot["editor"]).json
    assert detail["boundary"] == boundary


@pytest.mark.parametrize(
    ("boundary", "fragment"),
    [
        ({"type": "Point", "coordinates": [0, 0]}, "Polygon"),
        (square_polygon(0.5), "too small"),
        (square_polygon(5000), "too large"),
        ({"type": "Polygon", "coordinates": [[[0, 0], [1, 1], [0, 1], [1, 0], [0, 0]]]}, "crosses"),
        ({"type": "Polygon", "coordinates": [[[0, 0], [400, 0], [400, 1], [0, 0]]]}, "longitude"),
    ],
)
def test_a_bad_boundary_is_refused_before_anything_is_queued(
    client, plot, queued, boundary, fragment
):
    add_media(plot["id"], 6)
    resp = create(client, plot, boundary=boundary)
    assert resp.status_code == 422 and fragment in resp.json["message"]
    assert queued == []


def test_a_job_without_a_boundary_has_none(client, plot, queued):
    add_media(plot["id"], 6)
    assert create(client, plot).json["boundary"] is None


# --- the same file uploaded twice ----------------------------------------------------------


def sized(media_id, size):
    db.session.get(Media, media_id).size_bytes = size
    db.session.commit()


def test_a_video_uploaded_twice_is_only_used_once_and_the_log_says_so(client, plot, queued):
    add_media(plot["id"], 3)
    first = add_video(plot["id"], 10)
    second = add_video(plot["id"], 10)
    other = add_video(plot["id"], 12)
    for vid in (first, second):
        sized(vid, 5_000_000)
    sized(other, 5_000_000)  # same size, different length: a different recording
    resp = create(client, plot)
    assert resp.status_code == 202, resp.json
    job = db.session.get(MapJob, resp.json["id"])
    assert job.media_ids.count(first) == 1
    assert second not in job.media_ids and other in job.media_ids
    assert "Left out 1 repeated file" in job.log and "walk.mp4 (same as walk.mp4)" in job.log


def test_files_with_unknown_sizes_are_never_called_copies(client, plot, queued):
    add_media(plot["id"], 5)  # all size 0 and alike otherwise
    assert create(client, plot).json["media_count"] == 5


def test_repeats_are_dropped_before_the_minimum_is_checked(client, plot, queued):
    ids = add_media(plot["id"], 3)
    for i in ids:
        sized(i, 100_000)  # three photos that are really one
    resp = create(client, plot)
    assert resp.status_code == 422 and "at least" in resp.json["message"].lower()
