import pytest

from allotment.extensions import db
from allotment.models import FeatureNote

SQUARE = {"type": "Polygon", "coordinates": [[[0, 0], [0, 0.0001], [0.0001, 0.0001], [0.0001, 0], [0, 0]]]}


@pytest.fixture
def plot(client, register):
    owner, _ = register("owner@example.com", "Owner")
    viewer, _ = register("viewer@example.com", "Viewer")
    stranger, _ = register("stranger@example.com", "Stranger")
    pid = client.post("/api/v1/allotments", json={"name": "Plot 12"}, headers=owner).json["id"]
    base = f"/api/v1/allotments/{pid}"
    client.post(f"{base}/members", json={"email": "viewer@example.com"}, headers=owner)
    return {"base": base, "id": pid, "owner": owner, "viewer": viewer, "stranger": stranger}


def feature(client, plot, name="Bed 1"):
    resp = client.post(
        f"{plot['base']}/features",
        json={"type": "Feature", "geometry": SQUARE, "properties": {"name": name, "kind": "bed"}},
        headers=plot["owner"],
    )
    assert resp.status_code == 201, resp.json
    return resp.json["id"]


def note(client, plot, fid, body="Sowed carrots", **extra):
    resp = client.post(
        f"{plot['base']}/notes", json={"feature_id": fid, "body": body, **extra}, headers=plot["owner"]
    )
    assert resp.status_code == 201, resp.json
    return resp.json


def test_create_edit_delete(client, plot):
    fid = feature(client, plot)
    made = note(client, plot, fid, "  Sowed carrots  ")
    assert (made["body"], made["feature_id"], made["feature_name"], made["author"]) == ("Sowed carrots", fid, "Bed 1", "Owner")
    url = f"{plot['base']}/notes/{made['id']}"
    edited = client.patch(url, json={"body": "Sowed parsnips", "noted_at": "2026-11-01T09:30:00+00:00"}, headers=plot["owner"])
    assert edited.status_code == 200
    assert edited.json["body"] == "Sowed parsnips"
    assert edited.json["noted_at"].startswith("2026-11-01T09:30")
    assert client.delete(url, headers=plot["owner"]).status_code == 204
    assert client.get(f"{plot['base']}/notes", headers=plot["owner"]).json == []


def test_several_notes_on_one_day_newest_first(client, plot):
    fid = feature(client, plot)
    note(client, plot, fid, "Morning", noted_at="2026-11-01T08:00:00+00:00")
    note(client, plot, fid, "Evening", noted_at="2026-11-01T18:00:00+00:00")
    bodies = [n["body"] for n in client.get(f"{plot['base']}/notes", headers=plot["viewer"]).json]
    assert bodies == ["Evening", "Morning"]


def test_filter_by_feature(client, plot):
    a, b = feature(client, plot, "A"), feature(client, plot, "B")
    note(client, plot, a, "on A")
    note(client, plot, b, "on B")
    got = client.get(f"{plot['base']}/notes?feature_id={b}", headers=plot["viewer"]).json
    assert [n["body"] for n in got] == ["on B"]


def test_roles(client, plot):
    fid = feature(client, plot)
    made = note(client, plot, fid)
    url = f"{plot['base']}/notes/{made['id']}"
    body = {"feature_id": fid, "body": "x"}
    assert client.get(f"{plot['base']}/notes", headers=plot["viewer"]).status_code == 200
    assert client.post(f"{plot['base']}/notes", json=body, headers=plot["viewer"]).status_code == 403
    assert client.patch(url, json={"body": "x"}, headers=plot["viewer"]).status_code == 403
    assert client.delete(url, headers=plot["viewer"]).status_code == 403
    assert client.get(f"{plot['base']}/notes", headers=plot["stranger"]).status_code == 404


def test_body_is_required_and_not_empty(client, plot):
    fid = feature(client, plot)
    resp = client.post(f"{plot['base']}/notes", json={"feature_id": fid, "body": ""}, headers=plot["owner"])
    assert resp.status_code == 422


def test_other_allotments_features_and_notes_are_off_limits(client, register, plot):
    other_owner, _ = register("other@example.com", "Other")
    other = {"base": "", "owner": other_owner}
    oid = client.post("/api/v1/allotments", json={"name": "Elsewhere"}, headers=other_owner).json["id"]
    other["base"] = f"/api/v1/allotments/{oid}"
    foreign = feature(client, other)
    resp = client.post(f"{plot['base']}/notes", json={"feature_id": foreign, "body": "x"}, headers=plot["owner"])
    assert resp.status_code == 422
    theirs = note(client, other, foreign)
    assert client.patch(f"{plot['base']}/notes/{theirs['id']}", json={"body": "x"}, headers=plot["owner"]).status_code == 404
    assert client.delete(f"{plot['base']}/notes/{theirs['id']}", headers=plot["owner"]).status_code == 404


def test_deleting_the_feature_removes_its_notes(client, plot):
    fid = feature(client, plot)
    note(client, plot, fid)
    assert client.delete(f"{plot['base']}/features/{fid}", headers=plot["owner"]).status_code == 204
    assert db.session.query(FeatureNote).count() == 0


def test_locked_feature_still_takes_notes(client, plot):
    fid = feature(client, plot)
    client.patch(f"{plot['base']}/features/{fid}", json={"properties": {"locked": True}}, headers=plot["owner"])
    assert note(client, plot, fid)["id"]


def test_events_emitted(client, plot):
    from allotment import events

    seen = []
    events.subscribe("*", lambda e: seen.append(e.type))
    fid = feature(client, plot)
    made = note(client, plot, fid)
    client.patch(f"{plot['base']}/notes/{made['id']}", json={"body": "y"}, headers=plot["owner"])
    client.delete(f"{plot['base']}/notes/{made['id']}", headers=plot["owner"])
    assert {"note.created", "note.updated", "note.deleted"} <= set(seen)
