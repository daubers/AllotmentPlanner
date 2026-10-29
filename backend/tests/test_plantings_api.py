import io

import pytest

from allotment import events

from .helpers import make_jpeg
from .test_media import BED, plot  # noqa: F401 - owner, editor, viewer, stranger and a bed ("Bed 1")
from .test_plantings import DLAT, DLON


def region(x0, y0, x1, y1):
    """A rectangle in metres inside the shared test bed, whose south-west corner is (-1.0, 51.0)."""
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
    return {
        "type": "Polygon",
        "coordinates": [[[-1.0 + x * DLON, 51.0 + y * DLAT] for x, y in pts]],
    }


# the shared bed is ~ 0.0009 degrees of longitude (about 63 m) by 0.001 of latitude (about 111 m)
INSIDE = region(5, 5, 15, 12)
OTHER = region(10, 8, 20, 15)  # overlaps INSIDE
OUTSIDE = region(500, 500, 510, 510)


def packet(client, plot, name="Carrot", **kw):  # noqa: F811
    return client.post(
        f"{plot['base']}/packets", json={"name": name, **kw}, headers=plot["editor"]
    ).json["id"]


def sow(client, plot, reg=INSIDE, who="editor", **extra):  # noqa: F811
    body = {"feature_id": plot["bed"], "region": reg, **extra}
    return client.post(f"{plot['base']}/plantings", json=body, headers=plot[who])


def test_a_direct_sow_in_a_bed(client, plot):  # noqa: F811
    pid = packet(client, plot, variety="Nantes")
    resp = sow(client, plot, packet_id=pid, count=40, sown_on="2026-04-02", notes="in rows")
    assert resp.status_code == 201, resp.json
    p = resp.json
    assert (p["bed_name"], p["packet_name"], p["packet_variety"]) == ("Bed 1", "Carrot", "Nantes")
    assert (p["method"], p["status"], p["count"], p["sown_on"]) == (
        "direct_sow",
        "sown",
        40,
        "2026-04-02",
    )
    assert p["area_m2"] == pytest.approx(70, rel=0.05) and p["warnings"] == []
    got = client.get(f"{plot['base']}/plantings/{p['id']}", headers=plot["viewer"]).json
    assert got["region"]["type"] == "Polygon" and got["photos"] == []


def test_the_region_must_be_inside_a_bed_in_this_allotment(client, plot, register):  # noqa: F811
    out = sow(client, plot, OUTSIDE)
    assert out.status_code == 422 and "outside the bed" in out.json["message"]
    assert sow(client, plot, {"type": "Point", "coordinates": [0, 0]}).status_code == 422
    other, _ = register("other@example.com", "Other")
    oid = client.post("/api/v1/allotments", json={"name": "Elsewhere"}, headers=other).json["id"]
    foreign = client.post(
        f"/api/v1/allotments/{oid}/plantings",
        json={"feature_id": plot["bed"], "region": INSIDE},
        headers=other,
    )
    assert foreign.status_code == 422  # someone else's bed
    line = client.post(
        f"{plot['base']}/features",
        json={
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": [[-1.0, 51.0], [-0.9999, 51.0]]},
            "properties": {"name": "Path", "kind": "path"},
        },
        headers=plot["owner"],
    ).json["id"]
    not_area = sow(client, plot, INSIDE, feature_id=line)
    assert not_area.status_code == 422 and "area" in not_area.json["message"]


def test_a_packet_must_belong_to_the_allotment(client, plot, register):  # noqa: F811
    other, _ = register("other@example.com", "Other")
    oid = client.post("/api/v1/allotments", json={"name": "Elsewhere"}, headers=other).json["id"]
    theirs = client.post(
        f"/api/v1/allotments/{oid}/packets", json={"name": "Theirs"}, headers=other
    ).json["id"]
    assert sow(client, plot, packet_id=theirs).status_code == 422


def test_overlaps_are_allowed_with_a_warning_and_finished_plantings_do_not_count(client, plot):  # noqa: F811
    carrots = packet(client, plot, "Carrot")
    first = sow(client, plot, INSIDE, packet_id=carrots).json
    second = sow(client, plot, OTHER, packet_id=packet(client, plot, "Lettuce"))
    assert second.status_code == 201
    assert len(second.json["warnings"]) == 1 and "Overlaps Carrot" in second.json["warnings"][0]
    client.patch(
        f"{plot['base']}/plantings/{first['id']}",
        json={"status": "finished"},
        headers=plot["editor"],
    )
    third = sow(client, plot, OTHER)
    assert third.json["warnings"] != [] and "Lettuce" in third.json["warnings"][0]
    assert all("Carrot" not in w for w in third.json["warnings"])


def test_roles(client, plot):  # noqa: F811
    assert sow(client, plot, who="viewer").status_code == 403
    assert sow(client, plot, who="stranger").status_code == 404
    pid = sow(client, plot).json["id"]
    url = f"{plot['base']}/plantings/{pid}"
    assert client.patch(url, json={"notes": "x"}, headers=plot["viewer"]).status_code == 403
    assert client.delete(url, headers=plot["viewer"]).status_code == 403
    assert client.get(url, headers=plot["stranger"]).status_code == 404


def test_the_life_of_a_planting(client, plot):  # noqa: F811
    seen = []
    events.subscribe("*", lambda e: seen.append(e.type))
    pid = sow(client, plot, packet_id=packet(client, plot)).json["id"]
    url = f"{plot['base']}/plantings/{pid}"
    grown = client.patch(
        url, json={"status": "growing", "planted_on": "2026-05-01"}, headers=plot["editor"]
    )
    assert (grown.json["status"], grown.json["planted_on"]) == ("growing", "2026-05-01")
    client.patch(
        url, json={"status": "harvesting", "harvested_on": "2026-08-01"}, headers=plot["editor"]
    )
    moved = client.patch(url, json={"region": region(20, 20, 25, 25)}, headers=plot["editor"])
    assert moved.status_code == 200
    assert client.patch(url, json={"region": OUTSIDE}, headers=plot["editor"]).status_code == 422
    assert client.patch(url, json={"status": "gone"}, headers=plot["editor"]).status_code == 422
    assert client.delete(url, headers=plot["editor"]).status_code == 204
    assert client.get(url, headers=plot["viewer"]).status_code == 404
    assert [t for t in seen if t.startswith("planting.")] == [
        "planting.created",
        "planting.updated",
        "planting.updated",
        "planting.harvested",
        "planting.updated",
        "planting.deleted",
    ]


def test_list_filters(client, plot):  # noqa: F811
    a = packet(client, plot, "Carrot")
    first = sow(client, plot, INSIDE, packet_id=a).json["id"]
    second = sow(client, plot, region(30, 30, 35, 35), packet_id=packet(client, plot, "Leek")).json[
        "id"
    ]
    client.patch(
        f"{plot['base']}/plantings/{second}", json={"status": "failed"}, headers=plot["editor"]
    )

    def ids(**q):
        return [
            p["id"]
            for p in client.get(
                f"{plot['base']}/plantings", query_string=q, headers=plot["viewer"]
            ).json
        ]

    assert ids() == [first, second]
    assert ids(growing="true") == [first]
    assert ids(growing="false") == [second]
    assert ids(packet_id=a) == [first]
    assert ids(status="failed") == [second]
    assert ids(feature_id=plot["bed"]) == [first, second]


def test_photos_link_to_a_planting(client, plot):  # noqa: F811
    pid = sow(client, plot).json["id"]
    up = client.post(
        plot["url"],
        data={"file": (io.BytesIO(make_jpeg()), "bed.jpg"), "planting_id": str(pid)},
        headers=plot["editor"],
        content_type="multipart/form-data",
    )
    assert up.status_code == 201 and up.json["planting_id"] == pid
    got = client.get(f"{plot['base']}/plantings/{pid}", headers=plot["viewer"]).json
    assert [m["id"] for m in got["photos"]] == [up.json["id"]]
    assert [
        m["id"] for m in client.get(f"{plot['url']}?planting_id={pid}", headers=plot["viewer"]).json
    ] == [up.json["id"]]


# --- plant out from a tray ------------------------------------------------------------------


def tray_with(client, plot):  # noqa: F811
    tid = client.post(
        f"{plot['base']}/trays",
        json={"name": "Tray", "rows": 2, "cols": 3, "sown_on": "2026-03-01"},
        headers=plot["editor"],
    ).json["id"]
    tomato, basil = packet(client, plot, "Tomato"), packet(client, plot, "Basil")

    def cells(refs, **change):
        return client.patch(
            f"{plot['base']}/trays/{tid}/cells",
            json={"cells": [{"row": r, "col": c} for r, c in refs], "set": change},
            headers=plot["editor"],
        )

    cells([(0, 0), (0, 1)], packet_id=tomato, count=2)
    cells([(1, 0)], packet_id=basil)
    cells([(0, 0), (0, 1), (1, 0)], status="germinated")
    return tid, tomato, basil, cells


def plant_out(client, plot, tid, refs, reg=INSIDE, who="editor", **extra):  # noqa: F811
    body = {
        "cells": [{"row": r, "col": c} for r, c in refs],
        "feature_id": plot["bed"],
        "region": reg,
        **extra,
    }
    return client.post(f"{plot['base']}/trays/{tid}/plant-out", json=body, headers=plot[who])


def test_plant_out_makes_one_planting_per_packet_and_marks_the_cells(client, plot):  # noqa: F811
    tid, tomato, basil, _ = tray_with(client, plot)
    resp = plant_out(client, plot, tid, [(0, 0), (0, 1), (1, 0)], planted_on="2026-05-10")
    assert resp.status_code == 200, resp.json
    by_packet = {p["packet_id"]: p for p in resp.json["plantings"]}
    assert set(by_packet) == {tomato, basil}
    t = by_packet[tomato]
    assert (t["method"], t["status"], t["count"], t["tray_id"]) == ("transplant", "growing", 4, tid)
    assert (t["planted_on"], t["sown_on"]) == ("2026-05-10", "2026-03-01")
    tray = resp.json["tray"]
    assert tray["counts"]["planted_out"] == 3 and tray["counts"]["germinated"] == 0
    assert all(c["status"] == "planted_out" and c["planting_id"] for c in tray["cells"])
    assert tray["status"] == "planted_out"  # nothing left to plant


def test_plant_out_is_all_or_nothing(client, plot):  # noqa: F811
    tid, tomato, basil, cells = tray_with(client, plot)
    cells([(0, 1)], status="failed")
    bad = plant_out(client, plot, tid, [(0, 0), (0, 1)])
    assert bad.status_code == 422 and "Row 1, column 2: did not come up" in bad.json["message"]
    empty = plant_out(client, plot, tid, [(0, 0), (1, 2)])
    assert empty.status_code == 422 and "Row 2, column 3: nothing is sown" in empty.json["message"]
    outside = plant_out(client, plot, tid, [(0, 0)], reg=OUTSIDE)
    assert outside.status_code == 422
    tray = client.get(f"{plot['base']}/trays/{tid}", headers=plot["viewer"]).json
    assert tray["counts"]["planted_out"] == 0 and tray["status"] == "active"
    assert client.get(f"{plot['base']}/plantings", headers=plot["viewer"]).json == []


def test_a_partial_plant_out_leaves_the_tray_active_and_cells_go_out_once(client, plot):  # noqa: F811
    tid, *_ = tray_with(client, plot)
    assert plant_out(client, plot, tid, [(0, 0)]).status_code == 200
    tray = client.get(f"{plot['base']}/trays/{tid}", headers=plot["viewer"]).json
    assert tray["status"] == "active" and tray["counts"]["planted_out"] == 1
    again = plant_out(client, plot, tid, [(0, 0)])
    assert again.status_code == 422 and "already planted out" in again.json["message"]


def test_plant_out_needs_an_editor_and_the_events_say_so(client, plot):  # noqa: F811
    tid, *_ = tray_with(client, plot)
    assert plant_out(client, plot, tid, [(0, 0)], who="viewer").status_code == 403
    seen = []
    events.subscribe("*", lambda e: seen.append(e.type))
    plant_out(client, plot, tid, [(0, 0), (0, 1)])
    assert "tray.planted_out" in seen
