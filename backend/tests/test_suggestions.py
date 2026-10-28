import json
import math

import numpy as np
import pytest
from PIL import Image

from allotment import mapping_geo as geo
from allotment import mapping_pipeline as pipeline
from allotment.detection_labels import TYPES
from allotment.detector import Detection
from allotment.extensions import db
from allotment.models import ActivityLog, MapFeature, MapJob, MapSuggestion

from .test_detection_geo import OBJECTS, RING, cylinder, render_mask

TYPE = {t.name: t for t in TYPES}
REF = (51.5, -0.12)  # latitude, longitude of the scene's origin


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
        "s": f"{base}/suggestions",
        "owner": owner,
        "editor": editor,
        "viewer": viewer,
        "stranger": stranger,
    }


def add_suggestion(pid, **kw):
    s = MapSuggestion(
        allotment_id=pid,
        kind=kw.pop("kind", "tree"),
        name=kw.pop("name", "Tree"),
        geometry=kw.pop("geometry", {"type": "Point", "coordinates": [-0.12, 51.5]}),
        radius_m=kw.pop("radius_m", 0.5),
        **kw,
    )
    db.session.add(s)
    db.session.commit()
    return s.id


SQUARE = {
    "type": "Polygon",
    "coordinates": [
        [[-0.12, 51.5], [-0.12, 51.5001], [-0.1199, 51.5001], [-0.1199, 51.5], [-0.12, 51.5]]
    ],
}


# --- the API ---------------------------------------------------------------------------------


def test_pending_suggestions_are_listed_best_first(client, plot):
    low = add_suggestion(plot["id"], name="Low", confidence=0.3)
    high = add_suggestion(plot["id"], name="High", confidence=0.8)
    add_suggestion(plot["id"], name="Old", status="dismissed")
    out = client.get(plot["s"], headers=plot["editor"]).json
    assert [s["id"] for s in out] == [high, low]
    assert out[0]["geometry"]["type"] == "Point" and out[0]["radius_m"] == 0.5
    assert [
        s["name"]
        for s in client.get(
            plot["s"], query_string={"status": "dismissed"}, headers=plot["editor"]
        ).json
    ] == ["Old"]


def test_roles_and_isolation(client, plot, register):
    sid = add_suggestion(plot["id"])
    assert client.get(plot["s"], headers=plot["viewer"]).status_code == 403
    assert client.get(plot["s"], headers=plot["stranger"]).status_code == 404
    assert (
        client.patch(f"{plot['s']}/{sid}", json={"name": "x"}, headers=plot["viewer"]).status_code
        == 403
    )
    other, _ = register("other@example.com", "Other")
    mine = client.post("/api/v1/allotments", json={"name": "Other"}, headers=other).json["id"]
    foreign = add_suggestion(mine)
    assert (
        client.post(
            f"{plot['s']}/accept", json={"ids": [foreign]}, headers=plot["owner"]
        ).status_code
        == 404
    )
    assert db.session.get(MapSuggestion, foreign).status == "pending"


def test_rename_and_retype_before_accepting(client, plot):
    sid = add_suggestion(plot["id"], kind="water", name="Water butt 1")
    out = client.patch(
        f"{plot['s']}/{sid}",
        json={"name": "Rain barrel", "kind": "compost"},
        headers=plot["editor"],
    ).json
    assert (out["name"], out["kind"]) == ("Rain barrel", "compost")
    assert (
        client.patch(
            f"{plot['s']}/{sid}", json={"kind": "spaceship"}, headers=plot["editor"]
        ).status_code
        == 422
    )
    assert (
        client.patch(f"{plot['s']}/{sid}", json={"name": ""}, headers=plot["editor"]).status_code
        == 422
    )


def test_accepting_creates_map_features_and_records_it(client, plot):
    circle = add_suggestion(plot["id"], kind="water", name="Water butt", radius_m=0.4)
    rect = add_suggestion(plot["id"], kind="shed", name="Shed", geometry=SQUARE, radius_m=None)
    resp = client.post(f"{plot['s']}/accept", json={"ids": [circle, rect]}, headers=plot["editor"])
    assert resp.status_code == 200, resp.json
    by_name = {f["properties"]["name"]: f for f in resp.json}
    assert (
        by_name["Water butt"]["geometry"]["type"] == "Point"
        and by_name["Water butt"]["properties"]["radius_m"] == 0.4
    )
    assert (
        by_name["Shed"]["geometry"]["type"] == "Polygon"
        and by_name["Shed"]["properties"]["kind"] == "shed"
    )
    features = client.get(f"{plot['base']}/features", headers=plot["viewer"]).json["features"]
    assert sorted(f["properties"]["name"] for f in features) == ["Shed", "Water butt"]
    for sid in (circle, rect):
        s = db.session.get(MapSuggestion, sid)
        assert s.status == "accepted" and s.feature_id
    assert db.session.query(ActivityLog).filter_by(type="feature.created").count() == 2
    assert client.get(plot["s"], headers=plot["editor"]).json == []  # nothing left to review


def test_accepting_twice_is_refused_and_a_bad_one_adds_nothing(client, plot):
    good = add_suggestion(plot["id"], name="Good")
    bad = add_suggestion(
        plot["id"],
        name="Bad",
        kind="shed",
        geometry={"type": "Polygon", "coordinates": [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]]},
        radius_m=None,
    )  # bow-tie
    resp = client.post(f"{plot['s']}/accept", json={"ids": [good, bad]}, headers=plot["editor"])
    assert resp.status_code == 422
    assert (
        db.session.query(MapFeature).count() == 0
        and db.session.get(MapSuggestion, good).status == "pending"
    )
    assert (
        client.post(f"{plot['s']}/accept", json={"ids": [good]}, headers=plot["editor"]).status_code
        == 200
    )
    assert (
        client.post(f"{plot['s']}/accept", json={"ids": [good]}, headers=plot["editor"]).status_code
        == 409
    )
    assert (
        client.post(f"{plot['s']}/accept", json={"ids": []}, headers=plot["editor"]).status_code
        == 422
    )


def test_dismissing(client, plot):
    a, b = add_suggestion(plot["id"], name="A"), add_suggestion(plot["id"], name="B")
    client.post(f"{plot['s']}/accept", json={"ids": [b]}, headers=plot["editor"])
    assert (
        client.post(
            f"{plot['s']}/dismiss", json={"ids": [a, b]}, headers=plot["editor"]
        ).status_code
        == 204
    )
    assert db.session.get(MapSuggestion, a).status == "dismissed"
    assert db.session.get(MapSuggestion, b).status == "accepted"  # already on the map: left alone
    assert (
        client.patch(f"{plot['s']}/{a}", json={"name": "x"}, headers=plot["editor"]).status_code
        == 409
    )


# --- the detection stage, with a stand-in detector ----------------------------------------------


def rodrigues_vector(r: np.ndarray) -> list[float]:
    theta = math.acos(max(-1.0, min(1.0, (np.trace(r) - 1) / 2)))
    if theta < 1e-9:
        return [0.0, 0.0, 0.0]
    axis = np.array([r[2, 1] - r[1, 2], r[0, 2] - r[2, 0], r[1, 0] - r[0, 1]]) / (
        2 * math.sin(theta)
    )
    return (axis * theta).tolist()


def write_overrides(work, spread_m, headings=None):
    """GPS for the photos, about ``spread_m`` metres apart, as dataset preparation writes it."""
    lat_m, lon_m = geo.metres_per_degree(REF[0])
    overrides = {}
    for i, angle in enumerate(np.linspace(0, 2 * math.pi, 6, endpoint=False)):
        east, north = spread_m * math.cos(angle), spread_m * math.sin(angle)
        gps = {"latitude": REF[0] + north / lat_m, "longitude": REF[1] + east / lon_m}
        overrides[f"view{i}.jpg"] = {"gps": gps}
    (work / "exif_overrides.json").write_text(json.dumps(overrides))
    (work / "headings.json").write_text(json.dumps(headings or {}))


def write_reconstruction(work, shots, spread_m=60.0, ground=None):
    (work / "undistorted" / "images").mkdir(parents=True)
    rng = np.random.default_rng(0)
    if ground is None:
        ground = np.c_[rng.uniform(-6, 6, (80, 2)), rng.normal(0, 0.01, 80)]
    camera = {"projection_type": "perspective", "width": 640, "height": 480, "focal": 0.8}
    shot_json = {
        s.name: {
            "rotation": rodrigues_vector(s.rotation),
            "translation": s.translation.tolist(),
            "camera": "c",
        }
        for s in shots
    }
    points = {str(i): {"coordinates": p.tolist()} for i, p in enumerate(ground)}
    rec = [{"cameras": {"c": camera}, "shots": shot_json, "points": points}]
    (work / "undistorted" / "reconstruction.json").write_text(json.dumps(rec))
    write_overrides(work, spread_m)
    (work / "reference_lla.json").write_text(
        json.dumps({"latitude": REF[0], "longitude": REF[1], "altitude": 0})
    )
    for s in shots:
        Image.new("RGB", (640, 480), (90, 120, 80)).save(work / "undistorted" / "images" / s.name)


class SceneDetector:
    """Plays the part of the model: returns each object's true silhouette in each photo."""

    def __init__(self, shots, objects=OBJECTS):
        self.by_name = {s.name: s for s in shots}
        self.objects = objects
        self.seen = []

    def detect(self, image):
        name = image.filename.rsplit("/", 1)[-1]
        self.seen.append(name)
        shot = self.by_name[name]
        return [
            Detection(TYPE[label.capitalize()], 0.8, render_mask(shot, pts), 1.0)
            for label, (_, _, pts) in self.objects.items()
        ]


@pytest.fixture
def job(plot, tmp_path):
    j = MapJob(allotment_id=plot["id"], name="Recognise", media_ids=[])
    db.session.add(j)
    db.session.commit()
    work = tmp_path / "work"
    work.mkdir()
    return j, work


def metres(lon, lat):
    lat_m, lon_m = geo.metres_per_degree(REF[0])
    return (lon - REF[1]) * lon_m, (lat - REF[0]) * lat_m


def test_detection_turns_photos_into_suggestions_in_the_right_places(job):
    j, work = job
    write_reconstruction(work, RING)
    found = pipeline.detect_objects(j, work, detector=SceneDetector(RING))
    assert found == 3 and j.objects_found == 3
    rows = {s.name: s for s in db.session.query(MapSuggestion).filter_by(job_id=j.id)}
    assert set(rows) == {"Water butt", "Shed", "Tree"}  # a single one of each is not numbered
    butt, tree, shed = rows["Water butt"], rows["Tree"], rows["Shed"]
    assert (butt.kind, tree.kind, shed.kind) == ("water", "tree", "shed")
    assert butt.geometry["type"] == "Point" and butt.radius_m == pytest.approx(0.4, abs=0.15)
    assert metres(*butt.geometry["coordinates"]) == pytest.approx((0.5, 0.0), abs=0.3)
    assert metres(*tree.geometry["coordinates"]) == pytest.approx((2.0, -2.5), abs=0.35)
    ring = shed.geometry["coordinates"][0]
    assert shed.geometry["type"] == "Polygon" and ring[0] == ring[-1] and len(ring) == 5
    cx, cy = np.mean([metres(*p) for p in ring[:-1]], axis=0)
    assert (cx, cy) == pytest.approx((-2.0, 1.5), abs=0.7)
    assert all(s.views == 6 and s.status == "pending" for s in rows.values())


def test_several_of_a_kind_are_numbered_and_a_rerun_replaces_the_old_suggestions(job):
    j, work = job
    write_reconstruction(work, RING)
    objects = {"water butt": ("water", "circle", cylinder(0.5, 0.0, 0.4, 1.0))}
    detector = SceneDetector(RING, objects)
    base = detector.detect

    def both(image):  # a second butt elsewhere in the same photos
        shot = detector.by_name[image.filename.rsplit("/", 1)[-1]]
        return [
            *base(image),
            Detection(
                TYPE["Water butt"], 0.7, render_mask(shot, cylinder(-3.0, -1.0, 0.4, 1.0)), 1.0
            ),
        ]

    detector.detect = both
    pipeline.detect_objects(j, work, detector=detector)
    names = sorted(s.name for s in db.session.query(MapSuggestion).filter_by(status="pending"))
    assert names == ["Water butt 1", "Water butt 2"]
    j2 = MapJob(allotment_id=j.allotment_id, name="again", media_ids=[])
    db.session.add(j2)
    db.session.commit()
    pipeline.detect_objects(j2, work, detector=SceneDetector(RING))
    pending = db.session.query(MapSuggestion).filter_by(status="pending").all()
    assert {s.job_id for s in pending} == {j2.id}  # the first run's leftovers were set aside
    assert db.session.query(MapSuggestion).filter_by(status="dismissed").count() == 2


def test_nothing_found_is_not_an_error(job):
    j, work = job
    write_reconstruction(work, RING)
    assert pipeline.detect_objects(j, work, detector=SceneDetector(RING, {})) == 0
    assert db.session.query(MapSuggestion).count() == 0


def test_the_photos_looked_at_are_capped_and_real_photos_come_first():
    shots = [geo.Shot(f"m{i}.jpg", np.eye(3), np.zeros(3), geo.Camera(1, 1, 1)) for i in range(5)]
    frames = [
        geo.Shot(f"v1_{i:04d}.jpg", np.eye(3), np.zeros(3), geo.Camera(1, 1, 1)) for i in range(30)
    ]
    picked = pipeline.choose_shots(shots + frames, 12)
    assert [s.name for s in picked[:5]] == [s.name for s in shots]  # all five photos
    assert len(picked) == 12 and all(s.name.startswith("v") for s in picked[5:])
    assert len({s.name for s in picked}) == 12  # spread out, no repeats
    assert len(pipeline.choose_shots(shots, 3)) == 3 and pipeline.choose_shots([], 5) == []


def test_cancelling_stops_detection_between_photos(job):
    j, work = job
    write_reconstruction(work, RING)
    detector = SceneDetector(RING)
    real = detector.detect

    def detect_then_cancel(image):
        j.cancel_requested = True
        db.session.commit()
        return real(image)

    detector.detect = detect_then_cancel
    with pytest.raises(pipeline.JobCancelled):
        pipeline.detect_objects(j, work, detector=detector)
    assert len(detector.seen) == 1


# --- how a job chooses what to make -----------------------------------------------------------


def test_process_makes_only_what_was_asked_for(job, monkeypatch):
    j, work = job
    calls = []
    monkeypatch.setattr(pipeline, "prepare_dataset", lambda *a: calls.append("prepare") or 9)
    monkeypatch.setattr(pipeline, "reconstruct", lambda *a: calls.append("reconstruct"))
    monkeypatch.setattr(pipeline, "detect_objects", lambda *a: calls.append("detect") or 0)
    monkeypatch.setattr(
        pipeline,
        "build_orthophoto",
        lambda *a: calls.append("ortho") or (work / "o.tif", (0, 0, 1, 1), 0.05, 51.5),
    )
    monkeypatch.setattr(pipeline, "make_tiles", lambda *a: calls.append("tiles") or work)
    from allotment.models import MapLayer

    def fake_store(job, tiles, bounds, lo, hi):
        layer = MapLayer(
            allotment_id=job.allotment_id,
            job_id=job.id,
            name="x",
            west=0,
            south=0,
            east=1,
            north=1,
            min_zoom=lo,
            max_zoom=hi,
            visible=True,
        )
        db.session.add(layer)
        db.session.flush()
        return layer

    monkeypatch.setattr(pipeline, "store_layer", fake_store)
    j.detect_objects, j.overlay = True, False
    assert pipeline.process(j, work) is None
    assert calls == ["prepare", "reconstruct", "detect"]  # no overlay work at all
    calls.clear()
    j.detect_objects, j.overlay = False, True
    layer = pipeline.process(j, work)
    assert calls == ["prepare", "reconstruct", "ortho", "tiles"]
    assert layer.visible is False  # the experimental overlay is opt-in


def test_a_reconstruction_with_the_wrong_scale_is_fixed_from_the_camera_height(job):
    """The real failure: photos taken from one spot, so the GPS-derived scale is badly off."""
    j, work = job
    j.camera_height_m = 1.6  # RING's cameras are 1.6 m up
    db.session.commit()
    rng = np.random.default_rng(1)
    ground = np.c_[rng.uniform(-6, 6, (80, 2)), rng.normal(0, 0.01, 80)]
    truth = geo.Reconstruction(REF, list(RING), ground)
    # the same scene five times too big, scaled about the middle of the cameras like a bad GPS fit
    wrong = geo.transform(truth, scale=5.0)
    write_reconstruction(work, wrong.shots, spread_m=2.0, ground=wrong.points)  # GPS bunched up
    pipeline.detect_objects(j, work, detector=SceneDetector(RING))
    rows = {s.name: s for s in db.session.query(MapSuggestion).filter_by(job_id=j.id)}
    assert "scaling by 0.20" in j.log
    assert metres(*rows["Tree"].geometry["coordinates"]) == pytest.approx((2.0, -2.5), abs=0.45)
    assert metres(*rows["Water butt"].geometry["coordinates"]) == pytest.approx(
        (0.5, 0.0), abs=0.35
    )
    assert rows["Water butt"].radius_m == pytest.approx(0.4, abs=0.2)  # not 2 m


def test_widely_spread_photos_keep_the_gps_scale(job):
    j, work = job
    write_reconstruction(work, RING, spread_m=60.0)
    pipeline.detect_objects(j, work, detector=SceneDetector(RING))
    assert "keeping the GPS scale" in j.log and "scaling by" not in j.log
