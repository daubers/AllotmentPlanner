import json
import os
from datetime import UTC, datetime

import pytest

from allotment import mapping_pipeline as pipeline
from allotment.extensions import db
from allotment.models import ActivityLog, MapJob, MapLayer, Media
from allotment.storage import get_storage
from allotment.tasks import run_map_job

from .helpers import make_jpeg

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
    with pytest.raises(pipeline.JobFailed, match="Only 0 of the images have a location"):
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
