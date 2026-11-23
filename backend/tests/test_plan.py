import pytest

from allotment import events

from .test_media import plot  # noqa: F401 - owner, editor, viewer, stranger and a bed ("Bed 1")
from .test_plantings import DLAT, DLON


def small_bed(client, plot, name="Small", side=10):  # noqa: F811
    """A square bed of side x side metres (100 m2 by default)."""
    ring = [(0, 0), (side, 0), (side, side), (0, side), (0, 0)]
    geometry = {
        "type": "Polygon",
        "coordinates": [[[-1.0 + x * DLON, 51.0 + y * DLAT] for x, y in ring]],
    }
    return client.post(
        f"{plot['base']}/features",
        json={"type": "Feature", "geometry": geometry, "properties": {"name": name, "kind": "bed"}},
        headers=plot["owner"],
    ).json["id"]


def body(plot, **kw):  # noqa: F811
    base = {
        "feature_id": plot["bed"],
        "crop_key": "lettuce",
        "area_m2": 2,
        "sow_on": "2026-04-01",
        "end_on": "2026-06-10",
    }
    return {**base, **kw}


def add(client, plot, who="editor", **kw):  # noqa: F811
    return client.post(f"{plot['base']}/plan-items", json=body(plot, **kw), headers=plot[who])


def test_plan_a_crop_in_a_bed(client, plot):  # noqa: F811
    resp = add(client, plot, plant_count=12, notes="by the shed")
    assert resp.status_code == 201, resp.json
    item = resp.json
    assert (item["name"], item["method"], item["status"]) == ("Lettuce", "direct_sow", "planned")
    assert (item["area_m2"], item["plant_count"], item["notes"]) == (2, 12, "by the shed")
    assert item["series_key"] is None and item["planting_id"] is None
    got = client.get(f"{plot['base']}/plan-items/{item['id']}", headers=plot["viewer"])
    assert got.status_code == 200 and got.json["id"] == item["id"]


def test_the_name_comes_from_the_packet_then_the_crop(client, plot):  # noqa: F811
    pid = client.post(
        f"{plot['base']}/packets",
        json={"name": "Lettuce", "variety": "Little Gem"},
        headers=plot["editor"],
    ).json["id"]
    named = add(client, plot, packet_id=pid, crop_key=None)
    assert named.json["name"] == "Lettuce (Little Gem)"
    assert add(client, plot, name="My salad").json["name"] == "My salad"
    assert add(client, plot, crop_key=None).status_code == 422  # nothing to name it by


def test_a_transplant_needs_a_plant_out_date(client, plot):  # noqa: F811
    bad = add(client, plot, method="transplant", crop_key="tomato")
    assert bad.status_code == 422 and "plant-out" in bad.json["message"]
    ok = add(client, plot, method="transplant", crop_key="tomato", plant_out_on="2026-05-20")
    assert ok.status_code == 201 and ok.json["plant_out_on"] == "2026-05-20"
    assert add(client, plot, end_on="2026-03-01").status_code == 422  # free before sown


def test_bad_references_are_refused(client, plot, register):  # noqa: F811
    assert add(client, plot, crop_key="unobtainium").status_code == 422
    assert add(client, plot, area_m2=0).status_code == 422
    assert add(client, plot, feature_id=999999).status_code == 422
    other, _ = register("other@example.com", "Other")
    oid = client.post("/api/v1/allotments", json={"name": "Elsewhere"}, headers=other).json["id"]
    foreign = client.post(
        f"/api/v1/allotments/{oid}/packets", json={"name": "Theirs"}, headers=other
    ).json["id"]
    assert add(client, plot, packet_id=foreign).status_code == 422
    path = client.post(
        f"{plot['base']}/features",
        json={
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-1.0, 51.0]},
            "properties": {"name": "Shed", "kind": "shed"},
        },
        headers=plot["owner"],
    ).json["id"]
    not_a_bed = add(client, plot, feature_id=path)
    assert not_a_bed.status_code == 422 and "not a bed" in not_a_bed.json["message"]


def test_roles(client, plot):  # noqa: F811
    assert add(client, plot, who="viewer").status_code == 403
    assert add(client, plot, who="stranger").status_code == 404
    pid = add(client, plot).json["id"]
    base = f"{plot['base']}/plan-items/{pid}"
    assert client.get(base, headers=plot["stranger"]).status_code == 404
    assert client.patch(base, json={"notes": "x"}, headers=plot["viewer"]).status_code == 403
    assert client.delete(base, headers=plot["viewer"]).status_code == 403
    assert client.get(f"{plot['base']}/plan", headers=plot["viewer"]).status_code == 200
    assert client.get(f"{plot['base']}/plan", headers=plot["stranger"]).status_code == 404


def test_items_of_another_allotment_are_not_reachable(client, plot, register):  # noqa: F811
    pid = add(client, plot).json["id"]
    other, _ = register("other@example.com", "Other")
    oid = client.post("/api/v1/allotments", json={"name": "Elsewhere"}, headers=other).json["id"]
    assert (
        client.get(f"/api/v1/allotments/{oid}/plan-items/{pid}", headers=other).status_code == 404
    )


def test_edit_and_delete(client, plot):  # noqa: F811
    item = add(client, plot).json
    base = f"{plot['base']}/plan-items/{item['id']}"
    resp = client.patch(
        base,
        json={"area_m2": 3.5, "sow_on": "2026-04-10", "status": "skipped"},
        headers=plot["editor"],
    )
    assert resp.status_code == 200, resp.json
    assert (resp.json["area_m2"], resp.json["sow_on"], resp.json["status"]) == (
        3.5,
        "2026-04-10",
        "skipped",
    )
    clash = client.patch(base, json={"end_on": "2026-01-01"}, headers=plot["editor"])
    assert clash.status_code == 422
    assert client.get(base, headers=plot["editor"]).json["end_on"] == "2026-06-10"  # unchanged
    assert client.delete(base, headers=plot["editor"]).status_code == 204
    assert client.get(base, headers=plot["editor"]).status_code == 404


def test_deleting_the_bed_removes_its_plan(client, plot):  # noqa: F811
    item = add(client, plot).json
    client.delete(f"{plot['base']}/features/{plot['bed']}", headers=plot["owner"])
    assert (
        client.get(f"{plot['base']}/plan-items/{item['id']}", headers=plot["owner"]).status_code
        == 404
    )


def test_a_succession_makes_dated_steps_in_one_series(client, plot):  # noqa: F811
    resp = client.post(
        f"{plot['base']}/plan-items/successions",
        json={"item": body(plot), "interval_days": 14, "count": 4},
        headers=plot["editor"],
    )
    assert resp.status_code == 201, resp.json
    rows = resp.json
    assert [r["sow_on"] for r in rows] == ["2026-04-01", "2026-04-15", "2026-04-29", "2026-05-13"]
    assert [r["end_on"] for r in rows] == ["2026-06-10", "2026-06-24", "2026-07-08", "2026-07-22"]
    assert len({r["series_key"] for r in rows}) == 1 and rows[0]["series_key"]


def test_a_succession_shifts_plant_out_dates_too(client, plot):  # noqa: F811
    t = body(plot, method="transplant", crop_key="courgette", plant_out_on="2026-05-20")
    rows = client.post(
        f"{plot['base']}/plan-items/successions",
        json={"item": t, "interval_days": 21, "count": 2},
        headers=plot["editor"],
    ).json
    assert [r["plant_out_on"] for r in rows] == ["2026-05-20", "2026-06-10"]


def test_a_bad_succession_saves_nothing(client, plot):  # noqa: F811
    resp = client.post(
        f"{plot['base']}/plan-items/successions",
        json={"item": body(plot, crop_key="unobtainium"), "interval_days": 7, "count": 3},
        headers=plot["editor"],
    )
    assert resp.status_code == 422
    beds = client.get(f"{plot['base']}/plan", headers=plot["editor"]).json["beds"]
    assert all(b["items"] == [] for b in beds)
    too_many = client.post(
        f"{plot['base']}/plan-items/successions",
        json={"item": body(plot), "interval_days": 7, "count": 31},
        headers=plot["editor"],
    )
    assert too_many.status_code == 422


def test_the_plan_lists_beds_with_area_and_window(client, plot):  # noqa: F811
    add(client, plot)  # Apr-Jun 2026
    add(client, plot, sow_on="2027-04-01", end_on="2027-06-10")  # next year
    plan = client.get(
        f"{plot['base']}/plan?from=2026-01-01&to=2026-12-31", headers=plot["viewer"]
    ).json
    assert (plan["from"], plan["to"]) == ("2026-01-01", "2026-12-31")
    (bed,) = plan["beds"]
    assert bed["feature_id"] == plot["bed"] and bed["name"] == "Bed 1"
    assert 7000 < bed["area_m2"] < 8500  # about 63 m by 111 m
    assert [i["sow_on"] for i in bed["items"]] == ["2026-04-01"] and bed["conflicts"] == []
    later = client.get(
        f"{plot['base']}/plan?from=2027-01-01&to=2027-12-31", headers=plot["viewer"]
    ).json
    assert [i["sow_on"] for i in later["beds"][0]["items"]] == ["2027-04-01"]


def test_the_default_window_is_twelve_months_from_this_month(client, plot):  # noqa: F811
    plan = client.get(f"{plot['base']}/plan", headers=plot["viewer"]).json
    start, end = plan["from"], plan["to"]
    assert start.endswith("-01")
    from datetime import date

    s, e = date.fromisoformat(start), date.fromisoformat(end)
    assert (e - s).days in range(364, 367) and s.year * 12 + s.month <= e.year * 12 + e.month
    assert (
        client.get(
            f"{plot['base']}/plan?from=2026-05-01&to=2026-04-01", headers=plot["viewer"]
        ).status_code
        == 422
    )


def test_overbooking_is_a_warning_on_the_plan_not_an_error(client, plot):  # noqa: F811
    bed = small_bed(client, plot)  # 100 m2
    a = add(client, plot, feature_id=bed, area_m2=60, sow_on="2026-04-01", end_on="2026-07-01")
    b = add(client, plot, feature_id=bed, area_m2=60, sow_on="2026-05-01", end_on="2026-06-01")
    assert a.status_code == 201 and b.status_code == 201  # allowed
    plan = client.get(
        f"{plot['base']}/plan?from=2026-01-01&to=2026-12-31&feature_id={bed}",
        headers=plot["viewer"],
    ).json
    (b1,) = plan["beds"]
    assert b1["area_m2"] == pytest.approx(100, rel=0.05)
    (c,) = b1["conflicts"]
    assert (c["from"], c["to"]) == ("2026-05-01", "2026-06-01")
    assert c["used_m2"] == 120 and c["over_m2"] == pytest.approx(20, rel=0.2)
    assert c["item_ids"] == sorted([a.json["id"], b.json["id"]])


def test_back_to_back_successions_fit_a_full_bed(client, plot):  # noqa: F811
    bed = small_bed(client, plot)
    client.post(
        f"{plot['base']}/plan-items/successions",
        json={
            "item": body(
                plot, feature_id=bed, area_m2=95, sow_on="2026-04-01", end_on="2026-04-15"
            ),
            "interval_days": 14,
            "count": 5,
        },
        headers=plot["editor"],
    )
    plan = client.get(
        f"{plot['base']}/plan?from=2026-01-01&to=2026-12-31", headers=plot["viewer"]
    ).json
    by_id = {b["feature_id"]: b for b in plan["beds"]}
    assert len(by_id[bed]["items"]) == 5 and by_id[bed]["conflicts"] == []


def test_a_point_bed_has_no_area_and_no_conflicts(client, plot):  # noqa: F811
    point = client.post(
        f"{plot['base']}/features",
        json={
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-1.0, 51.0]},
            "properties": {"name": "Pot", "kind": "bed"},
        },
        headers=plot["owner"],
    ).json["id"]
    add(client, plot, feature_id=point, area_m2=500)
    add(client, plot, feature_id=point, area_m2=500)
    plan = client.get(f"{plot['base']}/plan?feature_id={point}", headers=plot["viewer"]).json
    assert plan["beds"][0]["area_m2"] is None and plan["beds"][0]["conflicts"] == []


def test_events_are_emitted(client, plot):  # noqa: F811
    seen = []
    events.subscribe(events.WILDCARD, lambda e: seen.append(e.type))
    item = add(client, plot).json
    client.patch(
        f"{plot['base']}/plan-items/{item['id']}", json={"notes": "x"}, headers=plot["editor"]
    )
    client.delete(f"{plot['base']}/plan-items/{item['id']}", headers=plot["editor"])
    assert [t for t in seen if t.startswith("plan_item.")] == [
        "plan_item.created",
        "plan_item.updated",
        "plan_item.deleted",
    ]
