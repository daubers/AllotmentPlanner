import io

from allotment import events

from .helpers import make_jpeg
from .test_media import plot  # noqa: F401 - the shared allotment with an owner, editor and viewer


def tray(client, plot, who="editor", **body):  # noqa: F811
    body = {"name": "Spring tray", "rows": 3, "cols": 4, **body}
    return client.post(f"{plot['base']}/trays", json=body, headers=plot[who])


def packet(client, plot, name="Tomato", **body):  # noqa: F811
    return client.post(
        f"{plot['base']}/packets", json={"name": name, **body}, headers=plot["editor"]
    ).json["id"]


def cells(client, plot, tid, refs, who="editor", **change):  # noqa: F811
    return client.patch(
        f"{plot['base']}/trays/{tid}/cells",
        json={"cells": [{"row": r, "col": c} for r, c in refs], "set": change},
        headers=plot[who],
    )


def test_create_read_and_counts(client, plot):  # noqa: F811
    resp = tray(client, plot, tray_type="12-cell", location="greenhouse", sown_on="2026-03-01")
    assert resp.status_code == 201
    t = resp.json
    assert (t["rows"], t["cols"], t["status"], t["cells"], t["photos"]) == (3, 4, "active", [], [])
    assert t["counts"] == {"empty": 12, "sown": 0, "germinated": 0, "failed": 0, "planted_out": 0}
    got = client.get(f"{plot['base']}/trays/{t['id']}", headers=plot["viewer"])
    assert got.json["location"] == "greenhouse" and got.json["sown_on"] == "2026-03-01"


def test_roles_and_isolation(client, plot, register):  # noqa: F811
    assert tray(client, plot, who="viewer").status_code == 403
    assert tray(client, plot, who="stranger").status_code == 404
    tid = tray(client, plot).json["id"]
    assert cells(client, plot, tid, [(0, 0)], who="viewer", packet_id=None).status_code == 403
    other, _ = register("other@example.com", "Other")
    oid = client.post("/api/v1/allotments", json={"name": "Elsewhere"}, headers=other).json["id"]
    assert client.get(f"/api/v1/allotments/{oid}/trays/{tid}", headers=other).status_code == 404


def test_validation(client, plot):  # noqa: F811
    assert tray(client, plot, rows=0).status_code == 422
    assert tray(client, plot, cols=31).status_code == 422
    assert tray(client, plot, rows=30, cols=30).status_code == 422  # 900 cells is too many
    assert tray(client, plot, name="").status_code == 422
    assert tray(client, plot, status="lost").status_code == 422


def test_sow_several_kinds_into_one_tray(client, plot):  # noqa: F811
    tid = tray(client, plot, sown_on="2026-03-01").json["id"]
    tomato, basil = packet(client, plot), packet(client, plot, "Basil")
    assert (
        cells(client, plot, tid, [(0, 0), (0, 1), (0, 2)], packet_id=tomato, count=2).status_code
        == 200
    )
    out = cells(client, plot, tid, [(1, 0), (1, 1)], packet_id=basil).json
    assert out["counts"]["sown"] == 5 and out["counts"]["empty"] == 7
    assert [(k["name"], k["cells"], k["seeds"]) for k in out["kinds"]] == [
        ("Tomato", 3, 6),
        ("Basil", 2, 2),
    ]
    first = out["cells"][0]
    assert (first["row"], first["col"], first["status"], first["sown_on"], first["count"]) == (
        0,
        0,
        "sown",
        "2026-03-01",
        2,
    )


def test_germinate_fail_and_clear(client, plot):  # noqa: F811
    tid = tray(client, plot).json["id"]
    pid = packet(client, plot)
    cells(client, plot, tid, [(0, 0), (0, 1), (0, 2)], packet_id=pid)
    cells(client, plot, tid, [(0, 0)], status="germinated", germinated_on="2026-03-12")
    cells(client, plot, tid, [(0, 1)], status="failed", note="damped off")
    out = cells(client, plot, tid, [(0, 2)], status="empty").json
    by = {(c["row"], c["col"]): c for c in out["cells"]}
    assert by[(0, 0)]["status"] == "germinated" and by[(0, 0)]["germinated_on"] == "2026-03-12"
    assert by[(0, 1)]["status"] == "failed" and by[(0, 1)]["note"] == "damped off"
    assert (0, 2) not in by
    assert out["counts"] == {"empty": 10, "sown": 0, "germinated": 1, "failed": 1, "planted_out": 0}


def test_a_bad_change_changes_nothing(client, plot):  # noqa: F811
    tid = tray(client, plot).json["id"]
    cells(client, plot, tid, [(0, 0)], packet_id=packet(client, plot))
    # (0,0) can germinate, (2,3) is empty: the whole request is refused
    bad = cells(client, plot, tid, [(0, 0), (2, 3)], status="germinated")
    assert bad.status_code == 422 and "Row 3, column 4" in bad.json["message"]
    assert (
        client.get(f"{plot['base']}/trays/{tid}", headers=plot["owner"]).json["counts"][
            "germinated"
        ]
        == 0
    )


def test_cells_outside_the_grid_and_foreign_packets_are_refused(client, plot, register):  # noqa: F811
    tid = tray(client, plot).json["id"]
    assert cells(client, plot, tid, [(3, 0)], packet_id=packet(client, plot)).status_code == 422
    other, _ = register("other@example.com", "Other")
    oid = client.post("/api/v1/allotments", json={"name": "Elsewhere"}, headers=other).json["id"]
    theirs = client.post(
        f"/api/v1/allotments/{oid}/packets", json={"name": "Theirs"}, headers=other
    ).json["id"]
    assert cells(client, plot, tid, [(0, 0)], packet_id=theirs).status_code == 422


def test_resizing_keeps_cells_unless_it_would_drop_sown_ones(client, plot):  # noqa: F811
    tid = tray(client, plot).json["id"]
    cells(client, plot, tid, [(2, 3)], packet_id=packet(client, plot))
    url = f"{plot['base']}/trays/{tid}"
    refused = client.patch(url, json={"rows": 2}, headers=plot["editor"])
    assert refused.status_code == 422 and "drop 1" in refused.json["message"]
    grown = client.patch(url, json={"rows": 5, "cols": 6}, headers=plot["editor"])
    assert grown.json["counts"]["empty"] == 29
    cells(client, plot, tid, [(2, 3)], status="empty")
    assert client.patch(url, json={"rows": 2, "cols": 2}, headers=plot["editor"]).status_code == 200


def test_list_filters_by_status_and_packet(client, plot):  # noqa: F811
    a = tray(client, plot, name="A").json["id"]
    b = tray(client, plot, name="B").json["id"]
    pid = packet(client, plot)
    cells(client, plot, b, [(0, 0)], packet_id=pid)
    client.patch(f"{plot['base']}/trays/{a}", json={"status": "finished"}, headers=plot["editor"])

    def names(**q):
        resp = client.get(f"{plot['base']}/trays", query_string=q, headers=plot["viewer"])
        return sorted(t["name"] for t in resp.json)

    assert names() == ["A", "B"]
    assert names(status="finished") == ["A"]
    assert names(packet_id=pid) == ["B"]
    assert (
        client.get(f"{plot['base']}/trays?packet_id={pid}", headers=plot["viewer"]).json[0][
            "kinds"
        ][0]["name"]
        == "Tomato"
    )


def test_photos_link_to_a_tray_and_survive_its_deletion(client, plot):  # noqa: F811
    tid = tray(client, plot).json["id"]
    up = client.post(
        plot["url"],
        data={"file": (io.BytesIO(make_jpeg()), "tray.jpg"), "tray_id": str(tid)},
        headers=plot["editor"],
        content_type="multipart/form-data",
    )
    assert up.status_code == 201 and up.json["tray_id"] == tid
    got = client.get(f"{plot['base']}/trays/{tid}", headers=plot["viewer"]).json
    assert [m["id"] for m in got["photos"]] == [up.json["id"]]
    assert [
        m["id"] for m in client.get(f"{plot['url']}?tray_id={tid}", headers=plot["viewer"]).json
    ] == [up.json["id"]]
    assert client.delete(f"{plot['base']}/trays/{tid}", headers=plot["editor"]).status_code == 204
    assert (
        client.get(f"{plot['url']}/{up.json['id']}", headers=plot["viewer"]).json["tray_id"] is None
    )


def test_deleting_a_packet_leaves_its_cells_sown(client, plot):  # noqa: F811
    tid = tray(client, plot).json["id"]
    pid = packet(client, plot)
    cells(client, plot, tid, [(0, 0)], packet_id=pid)
    client.delete(f"{plot['base']}/packets/{pid}", headers=plot["editor"])
    out = client.get(f"{plot['base']}/trays/{tid}", headers=plot["viewer"]).json
    assert out["cells"][0]["packet_id"] is None and out["counts"]["sown"] == 1


def test_events_and_activity(client, plot):  # noqa: F811
    seen = []
    events.subscribe("*", lambda e: seen.append(e.type))
    tid = tray(client, plot).json["id"]
    cells(client, plot, tid, [(0, 0)], packet_id=packet(client, plot))
    client.delete(f"{plot['base']}/trays/{tid}", headers=plot["editor"])
    assert [t for t in seen if t.startswith("tray.")] == [
        "tray.created",
        "tray.cells_updated",
        "tray.deleted",
    ]


def photo(client, plot, tid, taken="2026:10:20 10:00:00", **kw):  # noqa: F811
    up = client.post(
        plot["url"],
        data={"file": (io.BytesIO(make_jpeg(taken=taken)), "t.jpg"), "tray_id": str(tid)},
        headers=plot["editor"],
        content_type="multipart/form-data",
    )
    assert up.status_code == 201, up.json
    return up.json


def listed(client, plot):  # noqa: F811
    resp = client.get(f"{plot['base']}/trays", headers=plot["viewer"])
    return {t["id"]: t["thumb_url"] for t in resp.json}


def thumb_of(media):
    return f"/api/v1/media/{media['id']}/thumb"


def test_the_list_shows_a_thumbnail_of_a_trays_photo(client, plot):  # noqa: F811
    bare = tray(client, plot, name="Bare").json["id"]
    pictured = tray(client, plot, name="Pictured").json["id"]
    shot = photo(client, plot, pictured)
    thumbs = listed(client, plot)
    assert thumbs[bare] is None
    assert thumbs[pictured].split("?")[0] == thumb_of(shot)
    assert client.get(thumbs[pictured]).status_code == 200
    detail = client.get(f"{plot['base']}/trays/{pictured}", headers=plot["viewer"]).json
    assert detail["thumb_url"].split("?")[0] == thumb_of(shot)
    assert (
        client.get(f"{plot['base']}/trays/{bare}", headers=plot["viewer"]).json["thumb_url"] is None
    )


def test_the_newest_photo_is_the_thumbnail(client, plot):  # noqa: F811
    tid = tray(client, plot).json["id"]
    photo(client, plot, tid, taken="2026:10:05 09:00:00")
    newest = photo(client, plot, tid, taken="2026:10:25 09:00:00")
    photo(client, plot, tid, taken="2026:10:10 09:00:00")
    assert listed(client, plot)[tid].split("?")[0] == thumb_of(newest)
    detail = client.get(f"{plot['base']}/trays/{tid}", headers=plot["viewer"]).json
    assert detail["thumb_url"].split("?")[0] == thumb_of(newest)


def test_photos_without_a_thumbnail_and_other_trays_photos_are_skipped(client, plot):  # noqa: F811
    from allotment.extensions import db
    from allotment.models import Media

    mine, other = tray(client, plot).json["id"], tray(client, plot, name="Other").json["id"]
    older = photo(client, plot, mine, taken="2026:10:05 09:00:00")
    unprocessed = photo(client, plot, mine, taken="2026:10:25 09:00:00")
    photo(client, plot, other, taken="2026:10:28 09:00:00")
    db.session.get(Media, unprocessed["id"]).thumb_key = None  # still being processed
    db.session.commit()
    assert listed(client, plot)[mine].split("?")[0] == thumb_of(older)
    only = tray(client, plot, name="Pending only").json["id"]
    pending = photo(client, plot, only)
    db.session.get(Media, pending["id"]).thumb_key = None
    db.session.commit()
    assert listed(client, plot)[only] is None


def test_the_list_reads_photos_in_one_query(client, plot, app):  # noqa: F811
    from sqlalchemy import event

    from allotment.extensions import db

    def count():
        seen = []

        def before(conn, cursor, statement, *args):
            if "FROM media" in statement:
                seen.append(statement)

        event.listen(db.engine, "before_cursor_execute", before)
        try:
            listed(client, plot)
        finally:
            event.remove(db.engine, "before_cursor_execute", before)
        return len(seen)

    first = tray(client, plot).json["id"]
    photo(client, plot, first)
    assert count() == 1
    for n in range(3):
        photo(client, plot, tray(client, plot, name=f"T{n}").json["id"])
    assert count() == 1
