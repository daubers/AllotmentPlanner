from datetime import date

import pytest

BED = {
    "type": "Polygon",
    "coordinates": [[[-1.0, 51.0], [-1.0, 51.001], [-0.999, 51.001], [-0.999, 51.0], [-1.0, 51.0]]],
}


@pytest.fixture
def plot(client, register):
    owner, _ = register("owner@example.com", "Owner")
    viewer, _ = register("viewer@example.com", "Viewer")
    stranger, _ = register("stranger@example.com", "Stranger")
    pid = client.post("/api/v1/allotments", json={"name": "Plot 12"}, headers=owner).json["id"]
    base = f"/api/v1/allotments/{pid}"
    client.post(f"{base}/members", json={"email": "viewer@example.com"}, headers=owner)
    client.post(
        f"{base}/features",
        json={"type": "Feature", "geometry": BED, "properties": {"name": "Bed 1", "kind": "bed"}},
        headers=owner,
    )
    return {"base": base, "owner": owner, "viewer": viewer, "stranger": stranger}


def add(client, plot, title, **body):
    resp = client.post(
        f"{plot['base']}/tasks", json={"title": title, **body}, headers=plot["owner"]
    )
    assert resp.status_code == 201, resp.json
    return resp.json


def todo(client, plot, who="owner", **query):
    return client.get(f"{plot['base']}/todo", query_string=query, headers=plot[who])


def test_includes_overdue_and_today_but_not_future_done_or_undated(client, plot):
    add(client, plot, "overdue", due_date="2026-10-30")
    add(client, plot, "today", due_date="2026-11-02")
    add(client, plot, "future", due_date="2026-11-03")
    add(client, plot, "undated")
    done = add(client, plot, "finished", due_date="2026-11-02")
    client.post(f"{plot['base']}/tasks/{done['id']}/complete", headers=plot["owner"])
    resp = todo(client, plot, date="2026-11-02")
    assert resp.status_code == 200
    assert [t["title"] for t in resp.json["tasks"]] == ["overdue", "today"]
    assert resp.json["date"] == "2026-11-02"


def test_include_undated_and_priority_order(client, plot):
    add(client, plot, "low one", due_date="2026-11-02", priority="low")
    add(client, plot, "high one", due_date="2026-11-02", priority="high")
    add(client, plot, "undated")
    titles = [
        t["title"]
        for t in todo(client, plot, date="2026-11-02", include_undated="true").json["tasks"]
    ]
    assert titles == ["high one", "undated", "low one"]  # priority first, then due date


def test_carries_allotment_features_and_members_for_the_sheet(client, plot):
    body = todo(client, plot, date="2026-11-02").json
    assert body["allotment"]["name"] == "Plot 12"
    assert [f["properties"]["name"] for f in body["features"]] == ["Bed 1"]
    assert {m["display_name"] for m in body["members"]} == {"Owner", "Viewer"}


def test_defaults_to_today(client, plot):
    assert todo(client, plot).json["date"] == date.today().isoformat()


def test_access_control(client, plot):
    assert todo(client, plot, who="viewer").status_code == 200
    assert todo(client, plot, who="stranger").status_code == 404
    assert client.get(f"{plot['base']}/todo").status_code == 401
    assert todo(client, plot, date="not-a-date").status_code == 422
