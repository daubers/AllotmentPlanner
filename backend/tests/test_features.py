import pytest

BED = {
    "type": "Polygon",
    "coordinates": [[[-1.0, 51.0], [-1.0, 51.001], [-0.999, 51.001], [-0.999, 51.0], [-1.0, 51.0]]],
}


def feat(geometry=BED, **props):
    return {"type": "Feature", "geometry": geometry, "properties": props}


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
        "base": f"{base}/features",
        "owner": owner,
        "editor": editor,
        "viewer": viewer,
        "stranger": stranger,
    }


def test_create_and_read_polygon(client, plot):
    resp = client.post(plot["base"], json=feat(name="Bed 1", kind="bed"), headers=plot["editor"])
    assert resp.status_code == 201
    assert resp.json["geometry"]["type"] == "Polygon"
    assert resp.json["properties"] == {
        "name": "Bed 1",
        "kind": "bed",
        "radius_m": None,
        "style": {},
        "locked": False,
        "z": 0,
    }
    fid = resp.json["id"]
    assert client.get(f"{plot['base']}/{fid}", headers=plot["viewer"]).json["id"] == fid
    coll = client.get(plot["base"], headers=plot["viewer"]).json
    assert coll["type"] == "FeatureCollection" and len(coll["features"]) == 1


def test_circle_is_point_with_radius(client, plot):
    point = {"type": "Point", "coordinates": [-1.0, 51.0]}
    ok = client.post(
        plot["base"], json=feat(point, kind="tree", radius_m=2.5), headers=plot["owner"]
    )
    assert ok.status_code == 201 and ok.json["properties"]["radius_m"] == 2.5
    bad = client.post(plot["base"], json=feat(BED, radius_m=2.5), headers=plot["owner"])
    assert bad.status_code == 422
    neg = client.post(plot["base"], json=feat(point, radius_m=-1), headers=plot["owner"])
    assert neg.status_code == 422


@pytest.mark.parametrize(
    "geometry",
    [
        {"type": "Polygon", "coordinates": [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]]},  # bow-tie
        {"type": "Point", "coordinates": [200, 0]},  # lon out of range
        {"type": "MultiPoint", "coordinates": [[0, 0]]},  # unsupported type
        {"type": "Point"},  # missing coordinates
        {"type": "Polygon", "coordinates": []},  # empty
    ],
)
def test_invalid_geometry_rejected(client, plot, geometry):
    resp = client.post(plot["base"], json=feat(geometry), headers=plot["owner"])
    assert resp.status_code == 422


def test_invalid_properties_rejected(client, plot):
    assert (
        client.post(plot["base"], json=feat(kind="spaceship"), headers=plot["owner"]).status_code
        == 422
    )
    assert (
        client.post(plot["base"], json=feat(colour="red"), headers=plot["owner"]).status_code == 422
    )


def test_roles_enforced(client, plot):
    assert client.post(plot["base"], json=feat(), headers=plot["viewer"]).status_code == 403
    assert client.post(plot["base"], json=feat(), headers=plot["stranger"]).status_code == 404
    assert client.get(plot["base"], headers=plot["stranger"]).status_code == 404
    fid = client.post(plot["base"], json=feat(), headers=plot["editor"]).json["id"]
    assert (
        client.patch(
            f"{plot['base']}/{fid}", json={"properties": {"name": "x"}}, headers=plot["viewer"]
        ).status_code
        == 403
    )
    assert client.delete(f"{plot['base']}/{fid}", headers=plot["viewer"]).status_code == 403
    assert client.get(plot["base"]).status_code == 401


def test_patch_and_delete(client, plot):
    fid = client.post(plot["base"], json=feat(name="Old"), headers=plot["editor"]).json["id"]
    moved = {"type": "Point", "coordinates": [-0.5, 51.5]}
    patched = client.patch(
        f"{plot['base']}/{fid}",
        json={"geometry": moved, "properties": {"name": "New", "kind": "tree"}},
        headers=plot["editor"],
    )
    assert patched.status_code == 200
    assert patched.json["geometry"]["coordinates"] == [-0.5, 51.5]
    assert patched.json["properties"]["name"] == "New"
    # renaming alone keeps the geometry
    renamed = client.patch(
        f"{plot['base']}/{fid}", json={"properties": {"name": "Again"}}, headers=plot["editor"]
    )
    assert renamed.json["geometry"]["type"] == "Point"
    assert client.delete(f"{plot['base']}/{fid}", headers=plot["editor"]).status_code == 204
    assert client.get(f"{plot['base']}/{fid}", headers=plot["editor"]).status_code == 404


def test_features_isolated_between_allotments(client, plot, register):
    fid = client.post(plot["base"], json=feat(), headers=plot["owner"]).json["id"]
    other_owner, _ = register("other@example.com", "Other")
    other_id = client.post("/api/v1/allotments", json={"name": "Other"}, headers=other_owner).json[
        "id"
    ]
    url = f"/api/v1/allotments/{other_id}/features/{fid}"
    assert client.get(url, headers=other_owner).status_code == 404
    assert client.delete(url, headers=other_owner).status_code == 404


def test_bulk_put_creates_updates_and_deletes(client, plot):
    a = client.post(plot["base"], json=feat(name="A"), headers=plot["owner"]).json["id"]
    b = client.post(plot["base"], json=feat(name="B"), headers=plot["owner"]).json["id"]
    payload = {
        "type": "FeatureCollection",
        "features": [
            {**feat(name="A renamed"), "id": a},
            feat({"type": "Point", "coordinates": [-1, 51]}, name="C", kind="tree"),
        ],
    }
    resp = client.put(plot["base"], json=payload, headers=plot["editor"])
    assert resp.status_code == 200
    names = sorted(f["properties"]["name"] for f in resp.json["features"])
    assert names == ["A renamed", "C"]
    assert client.get(f"{plot['base']}/{b}", headers=plot["owner"]).status_code == 404


def test_bulk_put_is_atomic_on_bad_input(client, plot):
    a = client.post(plot["base"], json=feat(name="A"), headers=plot["owner"]).json["id"]
    payload = {
        "type": "FeatureCollection",
        "features": [
            {**feat(name="changed"), "id": a},
            feat({"type": "Point", "coordinates": [999, 0]}),
        ],
    }
    assert client.put(plot["base"], json=payload, headers=plot["owner"]).status_code == 422
    assert (
        client.get(f"{plot['base']}/{a}", headers=plot["owner"]).json["properties"]["name"] == "A"
    )
    foreign = {"type": "FeatureCollection", "features": [{**feat(), "id": 99999}]}
    assert client.put(plot["base"], json=foreign, headers=plot["owner"]).status_code == 422


def test_deleting_allotment_removes_features(client, plot):
    client.post(plot["base"], json=feat(), headers=plot["owner"])
    assert (
        client.delete(plot["base"].removesuffix("/features"), headers=plot["owner"]).status_code
        == 204
    )


def test_feature_events_emitted(client, plot):
    from allotment import events

    seen = []
    events.subscribe("*", lambda e: seen.append(e.type))
    fid = client.post(plot["base"], json=feat(), headers=plot["owner"]).json["id"]
    client.delete(f"{plot['base']}/{fid}", headers=plot["owner"])
    assert {"feature.created", "feature.deleted"} <= set(seen)


def test_a_locked_feature_cannot_be_moved_or_deleted_until_unlocked(client, plot):
    h = plot["editor"]
    fid = client.post(plot["base"], json=feat(name="Bed"), headers=h).json["id"]
    url = f"{plot['base']}/{fid}"
    assert client.patch(url, json={"properties": {"locked": True}}, headers=h).json[
        "properties"
    ]["locked"]
    moved = {"type": "Point", "coordinates": [-1.0, 51.0]}
    assert client.patch(url, json={"geometry": moved}, headers=h).status_code == 409
    assert client.delete(url, headers=h).status_code == 409
    # Names and kinds are still editable on a locked feature.
    ok = client.patch(url, json={"properties": {"name": "Renamed"}}, headers=h)
    assert ok.status_code == 200 and ok.json["geometry"]["type"] == "Polygon"
    # Unlocking and moving in one request works.
    both = client.patch(
        url, json={"geometry": BED, "properties": {"locked": False}}, headers=h
    )
    assert both.status_code == 200 and not both.json["properties"]["locked"]
    assert client.delete(url, headers=h).status_code == 204


def test_bulk_replace_keeps_locked_features_safe(client, plot):
    h = plot["editor"]
    fid = client.post(plot["base"], json=feat(), headers=h).json["id"]
    client.patch(f"{plot['base']}/{fid}", json={"properties": {"locked": True}}, headers=h)
    gone = client.put(plot["base"], json={"type": "FeatureCollection", "features": []}, headers=h)
    assert gone.status_code == 409
    assert len(client.get(plot["base"], headers=h).json["features"]) == 1


def test_locked_and_z_must_be_sensible(client, plot):
    h = plot["editor"]
    fid = client.post(plot["base"], json=feat(), headers=h).json["id"]
    url = f"{plot['base']}/{fid}"
    assert client.patch(url, json={"properties": {"locked": "yes"}}, headers=h).status_code == 422
    assert client.patch(url, json={"properties": {"z": 1.5}}, headers=h).status_code == 422
    assert client.patch(url, json={"properties": {"z": -3}}, headers=h).json["properties"]["z"] == -3
