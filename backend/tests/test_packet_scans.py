import io

import pytest
from PIL import Image

from allotment import packet_scan
from allotment.packet_text import PacketFacts

from .helpers import make_jpeg
from .test_media import plot  # noqa: F401 - the shared allotment with an owner, editor and viewer


def upload(client, plot, who="editor"):  # noqa: F811
    resp = client.post(
        plot["url"],
        data={"file": (io.BytesIO(make_jpeg(size=(120, 90))), "back.jpg")},
        headers=plot[who],
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201, resp.json
    return resp.json["id"]


def start(client, plot, media_id, who="editor"):  # noqa: F811
    return client.post(
        f"{plot['base']}/packet-scans", json={"media_id": media_id}, headers=plot[who]
    )


@pytest.fixture
def fake_scan(monkeypatch):
    """Stands in for the OCR and calendar reading (those need the worker image's libraries)."""
    calls = []

    def fake(image, engine=None, today=None):
        calls.append(image.size)
        crop = Image.new("RGB", (300, 60), (230, 230, 230))
        return packet_scan.ScanResult(
            name="Carrot",
            variety="Flyaway F1",
            facts=PacketFacts(
                supplier="Mr Fothergill's",
                sow_depth_mm=15,
                germinate_days_min=14,
                germinate_days_max=21,
                best_before_year=2028,
                seeds_in_packet=500,
            ),
            calendar={"sow_outdoors": [3, 4, 5], "harvest": [8, 9]},
            calendar_source="graphic",
            calendar_crop=crop,
            raw_text="Carrot Flyaway F1 ...",
            missing=["sow_depth_mm"],
        )

    monkeypatch.setattr(packet_scan, "scan", fake)
    return calls


def test_a_scan_makes_a_draft_packet_with_its_photo_and_calendar_crop(client, plot, fake_scan):  # noqa: F811
    media_id = upload(client, plot)
    resp = start(client, plot, media_id)
    assert resp.status_code == 202
    scan = client.get(f"{plot['base']}/packet-scans/{resp.json['id']}", headers=plot["viewer"]).json
    assert scan["status"] == "ready" and scan["error"] is None
    assert scan["calendar_source"] == "graphic" and scan["missing"] == ["sow_depth_mm"]
    assert scan["crop"]["caption"] == "Calendar as read from the packet"
    assert fake_scan == [(120, 90)]

    packet = client.get(f"{plot['base']}/packets/{scan['packet_id']}", headers=plot["viewer"]).json
    assert packet["status"] == "draft"
    assert (packet["name"], packet["variety"], packet["supplier"]) == (
        "Carrot",
        "Flyaway F1",
        "Mr Fothergill's",
    )
    assert (packet["sow_depth_mm"], packet["best_before_year"], packet["seeds_in_packet"]) == (
        15,
        2028,
        500,
    )
    assert packet["calendar"]["sow_outdoors"] == [3, 4, 5]
    assert {m["id"] for m in packet["photos"]} == {media_id, scan["crop"]["id"]}


def test_saving_a_draft_makes_it_active_and_drafts_can_be_listed(client, plot, fake_scan):  # noqa: F811
    scan = start(client, plot, upload(client, plot)).json
    pid = client.get(f"{plot['base']}/packet-scans/{scan['id']}", headers=plot["editor"]).json[
        "packet_id"
    ]
    url = f"{plot['base']}/packets"
    assert [p["id"] for p in client.get(f"{url}?status=draft", headers=plot["viewer"]).json] == [
        pid
    ]
    assert client.get(f"{url}?status=active", headers=plot["viewer"]).json == []
    saved = client.patch(
        f"{url}/{pid}", json={"status": "active", "sow_depth_mm": 12}, headers=plot["editor"]
    )
    assert saved.status_code == 200 and saved.json["status"] == "active"
    assert (
        client.patch(f"{url}/{pid}", json={"status": "draft"}, headers=plot["editor"]).status_code
        == 422
    )


def test_a_photo_that_cannot_be_read_fails_cleanly_and_can_be_retried(client, plot, monkeypatch):  # noqa: F811
    def boom(image, engine=None, today=None):
        raise RuntimeError("no OCR engine")

    monkeypatch.setattr(packet_scan, "scan", boom)
    scan = start(client, plot, upload(client, plot)).json
    got = client.get(f"{plot['base']}/packet-scans/{scan['id']}", headers=plot["editor"]).json
    assert got["status"] == "failed" and "RuntimeError" in got["error"] and got["packet_id"] is None

    monkeypatch.setattr(packet_scan, "scan", lambda *a, **k: packet_scan.ScanResult(raw_text=""))
    again = client.post(f"{plot['base']}/packet-scans/{scan['id']}/retry", headers=plot["editor"])
    assert again.status_code == 202
    got = client.get(f"{plot['base']}/packet-scans/{scan['id']}", headers=plot["editor"]).json
    assert got["status"] == "ready"
    pid = got["packet_id"]
    assert client.get(f"{plot['base']}/packets/{pid}", headers=plot["viewer"]).json["name"] == (
        "Unnamed packet"
    )
    assert (
        client.post(
            f"{plot['base']}/packet-scans/{scan['id']}/retry", headers=plot["editor"]
        ).status_code
        == 409
    )


def test_roles_and_ownership(client, plot, fake_scan, register):  # noqa: F811
    media_id = upload(client, plot)
    assert start(client, plot, media_id, who="viewer").status_code == 403
    assert start(client, plot, media_id, who="stranger").status_code == 404
    other, _ = register("other@example.com", "Other")
    oid = client.post("/api/v1/allotments", json={"name": "Elsewhere"}, headers=other).json["id"]
    foreign = client.post(
        f"/api/v1/allotments/{oid}/packet-scans", json={"media_id": media_id}, headers=other
    )
    assert foreign.status_code == 422
    assert start(client, plot, 99999).status_code == 422
    scan = start(client, plot, media_id).json
    assert (
        client.get(f"/api/v1/allotments/{oid}/packet-scans/{scan['id']}", headers=other).status_code
        == 404
    )
    assert [
        s["id"] for s in client.get(f"{plot['base']}/packet-scans", headers=plot["viewer"]).json
    ] == [scan["id"]]


def test_only_photos_can_be_read(client, plot, fake_scan, monkeypatch):  # noqa: F811
    from allotment.extensions import db
    from allotment.models import Media

    media_id = upload(client, plot)
    with client.application.app_context():
        db.session.get(Media, media_id).kind = "video"
        db.session.commit()
    resp = start(client, plot, media_id)
    assert resp.status_code == 422 and "photos" in resp.json["message"]
