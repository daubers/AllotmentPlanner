import math

import pytest
from shapely.geometry import shape

# A bed drawn slightly skewed; in fact 10 m by 5 m. Corners 1 to 4, going round.
M_LAT, M_LNG = 111_195.0, 69_000.0  # metres per degree near 51.6 N (approximate is fine here)
LAT0, LNG0 = 51.6, -1.1


def corner(x_m, y_m):
    return [LNG0 + x_m / M_LNG, LAT0 + y_m / M_LAT]


def polygon(*points):
    ring = [corner(*p) for p in points]
    return {"type": "Polygon", "coordinates": [[*ring, ring[0]]]}


SKEWED = polygon((0, 0), (10.6, 0.4), (10.1, 5.7), (-0.3, 4.6))


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
        "base": base,
        "url": f"{base}/measurements",
        "owner": owner,
        "editor": editor,
        "viewer": viewer,
        "stranger": stranger,
    }


def add_feature(client, plot, geometry, name="Bed 1", kind="bed", radius_m=None):
    props = {"name": name, "kind": kind}
    if radius_m:
        props["radius_m"] = radius_m
    resp = client.post(
        f"{plot['base']}/features",
        json={"type": "Feature", "geometry": geometry, "properties": props},
        headers=plot["owner"],
    )
    assert resp.status_code == 201, resp.json
    return resp.json["id"]


def sync(client, plot, who="editor"):
    return client.post(f"{plot['url']}/sync", headers=plot[who])


def listing(client, plot, who="viewer"):
    return client.get(plot["url"], headers=plot[who]).json


def patch(client, plot, item_id, who="editor", **body):
    return client.patch(f"{plot['url']}/{item_id}", json=body, headers=plot[who])


def measure_all(client, plot, values):
    """Record values for the first checklist items, in list order."""
    for item, value in zip(listing(client, plot)["items"], values, strict=False):
        assert patch(client, plot, item["id"], value_m=value).status_code == 200


RECT = [10, 5, 10, 5, math.hypot(10, 5)]  # four edges and the 1-3 diagonal


def test_sync_makes_the_checklist_from_the_drawn_shapes(client, plot):
    add_feature(client, plot, SKEWED)
    add_feature(
        client, plot, {"type": "Point", "coordinates": corner(20, 20)}, "Pond", "water", 1.5
    )
    add_feature(client, plot, {"type": "Point", "coordinates": corner(30, 30)}, "Tree", "tree")
    data = sync(client, plot).json
    kinds = [(i["feature_name"], i["kind"], i["label"]) for i in data["items"]]
    assert kinds == [
        ("Bed 1", "edge", "1 to 2"), ("Bed 1", "edge", "2 to 3"), ("Bed 1", "edge", "3 to 4"),
        ("Bed 1", "edge", "4 to 1"), ("Bed 1", "diagonal", "1 to 3"), ("Pond", "radius", "Radius"),
    ]  # fmt: skip
    assert data["total"] == 6 and data["measured"] == 0 and data["length_unit"] == "m"
    assert data["items"][0]["drawn_m"] == pytest.approx(math.hypot(10.6, 0.4), abs=0.05)
    assert data["items"][-1]["drawn_m"] == 1.5
    assert [f["total"] for f in data["features"]] == [5, 1]


def test_sync_is_idempotent_and_keeps_measurements(client, plot):
    add_feature(client, plot, SKEWED)
    sync(client, plot)
    measure_all(client, plot, RECT)
    again = sync(client, plot).json
    assert len(again["items"]) == 5 and again["measured"] == 5


def test_a_changed_shape_drops_unmeasured_items_and_flags_measured_ones_stale(client, plot):
    fid = add_feature(client, plot, SKEWED)
    sync(client, plot)
    items = listing(client, plot)["items"]
    patch(client, plot, items[0]["id"], value_m=10)
    triangle = polygon((0, 0), (10.6, 0.4), (10.1, 5.7))
    client.patch(
        f"{plot['base']}/features/{fid}", json={"geometry": triangle}, headers=plot["owner"]
    )
    data = sync(client, plot).json
    by_label = {(i["kind"], i["label"]): i for i in data["items"]}
    assert (
        not by_label[("edge", "1 to 2")]["stale"] and by_label[("edge", "1 to 2")]["value_m"] == 10
    )
    assert ("edge", "3 to 1") in by_label  # the new closing edge
    assert ("diagonal", "1 to 3") not in by_label  # unmeasured, so gone
    assert all(not i["stale"] for i in data["items"])
    # Measure the closing edge, redraw as the four-cornered bed: that edge's corners are gone.
    patch(client, plot, by_label[("edge", "3 to 1")]["id"], value_m=6)
    client.patch(f"{plot['base']}/features/{fid}", json={"geometry": SKEWED}, headers=plot["owner"])
    stale = [i for i in sync(client, plot).json["items"] if i["stale"]]
    assert [(i["label"], i["value_m"]) for i in stale] == [("3 to 1", 6.0)]


def test_preview_shows_the_change_and_writes_nothing(client, plot):
    fid = add_feature(client, plot, SKEWED)
    sync(client, plot)
    measure_all(client, plot, RECT)
    resp = client.post(f"{plot['url']}/fit?preview=true", headers=plot["editor"])
    assert resp.status_code == 200, resp.json
    r = resp.json["features"][0]
    assert resp.json["applied"] is False
    assert r["changed"] and r["rms_before_m"] > 0.2 and r["rms_after_m"] < 0.005
    assert r["missing"] == 0 and r["recheck"] == [] and r["error"] is None
    after = client.get(f"{plot['base']}/features/{fid}", headers=plot["viewer"]).json
    assert after["geometry"]["coordinates"] == SKEWED["coordinates"]


def test_apply_corrects_the_shape_to_the_tape(client, plot):
    fid = add_feature(client, plot, SKEWED)
    sync(client, plot)
    measure_all(client, plot, RECT)
    resp = client.post(f"{plot['url']}/fit?preview=false", headers=plot["editor"])
    assert resp.status_code == 200 and resp.json["applied"] is True
    geometry = client.get(f"{plot['base']}/features/{fid}", headers=plot["viewer"]).json["geometry"]
    ring = geometry["coordinates"][0]
    sides = [
        math.hypot((lng2 - lng1) * M_LNG, (lat2 - lat1) * M_LAT)
        for (lng1, lat1), (lng2, lat2) in zip(ring, ring[1:], strict=False)
    ]
    assert sides == pytest.approx([10, 5, 10, 5], abs=0.05)
    assert shape(geometry).is_valid
    again = client.post(f"{plot['url']}/fit?preview=true", headers=plot["editor"]).json
    assert again["features"][0]["changed"] is False  # it now matches the tape


def test_too_few_measurements_say_what_is_missing(client, plot):
    add_feature(client, plot, SKEWED)
    sync(client, plot)
    measure_all(client, plot, RECT[:4])
    r = client.post(f"{plot['url']}/fit", headers=plot["editor"]).json["features"][0]
    assert r["missing"] == 1


def test_a_spare_distance_exposes_a_wrong_measurement(client, plot):
    add_feature(client, plot, SKEWED)
    sync(client, plot)
    fid = listing(client, plot)["items"][0]["feature_id"]
    spare = client.post(
        plot["url"], json={"feature_id": fid, "a": 1, "b": 3}, headers=plot["editor"]
    )
    assert (
        spare.status_code == 201
        and spare.json["kind"] == "custom"
        and spare.json["label"] == "2 to 4"
    )
    items = listing(client, plot)["items"]
    assert items[-1]["kind"] == "custom"
    diagonal = math.hypot(10, 5)
    measure_all(client, plot, [10, 7, 10, 5, diagonal, diagonal])  # side 2 to 3 misread as 7
    r = client.post(f"{plot['url']}/fit", headers=plot["editor"]).json["features"][0]
    assert r["recheck"], "the disagreement should be flagged for re-measuring"


def test_a_circle_takes_its_radius_from_the_tape(client, plot):
    fid = add_feature(
        client, plot, {"type": "Point", "coordinates": corner(5, 5)}, "Pond", "water", 1.5
    )
    sync(client, plot)
    patch(client, plot, listing(client, plot)["items"][0]["id"], value_m=2.25)
    client.post(f"{plot['url']}/fit?preview=false", headers=plot["editor"])
    feature = client.get(f"{plot['base']}/features/{fid}", headers=plot["viewer"]).json
    assert feature["properties"]["radius_m"] == 2.25


def test_measuring_validates_and_records_who_and_when(client, plot):
    add_feature(client, plot, SKEWED)
    sync(client, plot)
    item_id = listing(client, plot)["items"][0]["id"]
    for bad in (0, -3, 5000):
        assert patch(client, plot, item_id, value_m=bad).status_code == 422
    ok = patch(client, plot, item_id, value_m=4.2, note="from the post").json
    assert (
        ok["value_m"] == 4.2
        and ok["note"] == "from the post"
        and ok["measured_at"]
        and ok["measured_by"]
    )
    cleared = patch(client, plot, item_id, value_m=None).json
    assert cleared["value_m"] is None and cleared["measured_at"] is None
    assert patch(client, plot, item_id, skipped=True).json["skipped"] is True
    assert listing(client, plot)["total"] == 4  # a skipped one leaves the count


def test_only_extra_distances_can_be_removed_and_duplicates_are_refused(client, plot):
    add_feature(client, plot, SKEWED)
    sync(client, plot)
    items = listing(client, plot)["items"]
    fid = items[0]["feature_id"]
    assert (
        client.delete(f"{plot['url']}/{items[0]['id']}", headers=plot["editor"]).status_code == 409
    )
    for a, b, status in ((1, 0, 409), (2, 2, 422), (0, 9, 422)):
        resp = client.post(
            plot["url"], json={"feature_id": fid, "a": a, "b": b}, headers=plot["editor"]
        )
        assert resp.status_code == status, (a, b, resp.json)
    extra = client.post(
        plot["url"], json={"feature_id": fid, "a": 1, "b": 3}, headers=plot["editor"]
    ).json
    assert client.delete(f"{plot['url']}/{extra['id']}", headers=plot["editor"]).status_code == 204


def test_roles(client, plot):
    add_feature(client, plot, SKEWED)
    assert sync(client, plot, "viewer").status_code == 403
    assert sync(client, plot, "stranger").status_code == 404
    sync(client, plot)
    item_id = listing(client, plot)["items"][0]["id"]
    assert client.get(plot["url"], headers=plot["stranger"]).status_code == 404
    assert patch(client, plot, item_id, who="viewer", value_m=3).status_code == 403
    assert client.post(f"{plot['url']}/fit", headers=plot["viewer"]).status_code == 403


def test_the_length_unit_is_set_by_the_owner_and_validated(client, plot):
    assert client.get(plot["base"], headers=plot["viewer"]).json["length_unit"] == "m"
    ok = client.patch(plot["base"], json={"length_unit": "ft_in"}, headers=plot["owner"])
    assert ok.status_code == 200 and ok.json["length_unit"] == "ft_in"
    assert (
        client.patch(plot["base"], json={"length_unit": "miles"}, headers=plot["owner"]).status_code
        == 422
    )
    assert (
        client.patch(plot["base"], json={"length_unit": "cm"}, headers=plot["editor"]).status_code
        == 403
    )


def test_applying_counts_as_a_map_edit_on_the_overview(client, plot):
    add_feature(client, plot, SKEWED)
    sync(client, plot)
    measure_all(client, plot, RECT)
    url = f"{plot['base']}/overview"

    def edits():
        return client.get(url, headers=plot["viewer"]).json["totals"]["map_edits"]

    before = edits()
    client.post(f"{plot['url']}/fit?preview=false", headers=plot["editor"])
    assert edits() == before + 1
