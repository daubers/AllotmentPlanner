from datetime import date, timedelta

import pytest

from allotment import events
from allotment.api.tasks import next_due

BED = {
    "type": "Polygon",
    "coordinates": [[[-1.0, 51.0], [-1.0, 51.001], [-0.999, 51.001], [-0.999, 51.0], [-1.0, 51.0]]],
}


@pytest.fixture
def plot(client, register):
    owner, _ = register("owner@example.com", "Owner")
    editor, editor_user = register("editor@example.com", "Editor")
    viewer, _ = register("viewer@example.com", "Viewer")
    stranger, stranger_user = register("stranger@example.com", "Stranger")
    pid = client.post("/api/v1/allotments", json={"name": "Plot"}, headers=owner).json["id"]
    base = f"/api/v1/allotments/{pid}"
    client.post(
        f"{base}/members", json={"email": "editor@example.com", "role": "editor"}, headers=owner
    )
    client.post(f"{base}/members", json={"email": "viewer@example.com"}, headers=owner)
    bed = client.post(
        f"{base}/features",
        json={"type": "Feature", "geometry": BED, "properties": {"name": "Bed 1", "kind": "bed"}},
        headers=owner,
    ).json["id"]
    return {
        "base": f"{base}/tasks",
        "root": base,
        "owner": owner,
        "editor": editor,
        "viewer": viewer,
        "stranger": stranger,
        "editor_id": editor_user["id"],
        "stranger_id": stranger_user["id"],
        "bed": bed,
    }


def make(client, plot, who="editor", **body):
    body.setdefault("title", "Water the beans")
    resp = client.post(plot["base"], json=body, headers=plot[who])
    assert resp.status_code == 201, resp.json
    return resp.json


def test_create_with_defaults_and_pin_to_feature(client, plot):
    task = make(client, plot, feature_id=plot["bed"], due_date="2026-11-01", priority="high")
    assert task["status"] == "todo" and task["feature_id"] == plot["bed"]
    assert task["due_date"] == "2026-11-01" and task["location"] is None
    assert (
        client.get(f"{plot['base']}/{task['id']}", headers=plot["viewer"]).json["title"]
        == task["title"]
    )


def test_pin_to_point_and_clear(client, plot):
    pin = {"type": "Point", "coordinates": [-0.9995, 51.0005]}
    task = make(client, plot, location=pin)
    assert task["location"]["coordinates"] == [-0.9995, 51.0005]
    cleared = client.patch(
        f"{plot['base']}/{task['id']}", json={"location": None}, headers=plot["editor"]
    )
    assert cleared.json["location"] is None


@pytest.mark.parametrize(
    "body",
    [
        {"title": ""},
        {"priority": "urgent"},
        {"status": "done"},
        {"recurrence": "hourly"},
        {"location": BED},
        {"location": {"type": "Point", "coordinates": [500, 0]}},
        {"feature_id": 99999},
        {"assignee_id": 99999},
    ],
)
def test_invalid_input_rejected(client, plot, body):
    payload = {"title": "x", **body}
    assert client.post(plot["base"], json=payload, headers=plot["editor"]).status_code == 422


def test_feature_from_another_allotment_rejected(client, plot, register):
    other, _ = register("other@example.com", "Other")
    oid = client.post("/api/v1/allotments", json={"name": "Other"}, headers=other).json["id"]
    foreign = client.post(
        f"/api/v1/allotments/{oid}/features",
        json={"type": "Feature", "geometry": BED, "properties": {}},
        headers=other,
    ).json["id"]
    resp = client.post(
        plot["base"], json={"title": "x", "feature_id": foreign}, headers=plot["owner"]
    )
    assert resp.status_code == 422


def test_assignee_must_be_member(client, plot):
    ok = make(client, plot, assignee_id=plot["editor_id"])
    assert ok["assignee_id"] == plot["editor_id"]
    bad = client.post(
        plot["base"], json={"title": "x", "assignee_id": plot["stranger_id"]}, headers=plot["owner"]
    )
    assert bad.status_code == 422


def test_roles_enforced(client, plot):
    task = make(client, plot)
    url = f"{plot['base']}/{task['id']}"
    assert client.post(plot["base"], json={"title": "x"}, headers=plot["viewer"]).status_code == 403
    for method, path in (
        ("patch", url),
        ("delete", url),
        ("post", f"{url}/complete"),
        ("post", f"{url}/reopen"),
    ):
        kwargs = {"json": {"title": "y"}} if method == "patch" else {}
        assert getattr(client, method)(path, headers=plot["viewer"], **kwargs).status_code == 403
    assert client.get(plot["base"], headers=plot["viewer"]).status_code == 200
    assert client.get(plot["base"], headers=plot["stranger"]).status_code == 404
    assert client.get(url, headers=plot["stranger"]).status_code == 404


def test_filters_and_ordering(client, plot):
    make(client, plot, title="late", due_date="2026-11-10", priority="normal")
    b = make(client, plot, title="soon", due_date="2026-11-01", priority="normal")
    make(client, plot, title="urgent", due_date="2026-11-20", priority="high")
    make(client, plot, title="someday", feature_id=plot["bed"])

    def titles(**q):
        resp = client.get(plot["base"], query_string=q, headers=plot["viewer"])
        return [t["title"] for t in resp.json]

    assert titles() == [
        "urgent",
        "soon",
        "late",
        "someday",
    ]  # priority first, then due date, undated last
    assert titles(due_on="2026-11-01") == ["soon"]
    assert titles(due_by="2026-11-10") == ["soon", "late"]  # overdue tasks are included
    assert titles(feature_id=plot["bed"]) == ["someday"]
    client.post(f"{plot['base']}/{b['id']}/complete", headers=plot["editor"])
    assert titles(open="true") == ["urgent", "late", "someday"]
    assert titles(open="false") == ["soon"]
    assert titles(status="done") == ["soon"]
    assert (
        client.get(plot["base"], query_string={"status": "x"}, headers=plot["viewer"]).status_code
        == 422
    )


def test_complete_and_reopen(client, plot):
    task = make(client, plot)
    done = client.post(f"{plot['base']}/{task['id']}/complete", headers=plot["editor"]).json
    assert (
        done["status"] == "done"
        and done["completed_at"]
        and done["completed_by"] == plot["editor_id"]
    )
    assert done["spawned_task_id"] is None
    again = client.post(f"{plot['base']}/{task['id']}/complete", headers=plot["editor"]).json
    assert again["completed_at"] == done["completed_at"]  # idempotent
    assert (
        client.patch(
            f"{plot['base']}/{task['id']}", json={"status": "doing"}, headers=plot["editor"]
        ).status_code
        == 409
    )
    reopened = client.post(f"{plot['base']}/{task['id']}/reopen", headers=plot["editor"]).json
    assert reopened["status"] == "todo" and reopened["completed_at"] is None


def test_recurring_task_spawns_next(client, plot):
    task = make(client, plot, due_date="2099-11-01", recurrence="weekly", feature_id=plot["bed"])
    done = client.post(f"{plot['base']}/{task['id']}/complete", headers=plot["editor"]).json
    nxt = client.get(f"{plot['base']}/{done['spawned_task_id']}", headers=plot["editor"]).json
    assert nxt["due_date"] == "2099-11-08" and nxt["status"] == "todo"
    assert nxt["feature_id"] == plot["bed"] and nxt["recurrence"] == "weekly"


@pytest.mark.parametrize(
    "current,rule,expected",
    [
        (date(2026, 11, 1), "daily", date(2026, 11, 2)),
        (date(2026, 11, 30), "daily", date(2026, 12, 1)),
        (date(2026, 11, 1), "weekly", date(2026, 11, 8)),
        (date(2026, 1, 31), "monthly", date(2026, 2, 28)),
        (date(2028, 1, 31), "monthly", date(2028, 2, 29)),
        (date(2026, 12, 15), "monthly", date(2027, 1, 15)),
    ],
)
def test_next_due(current, rule, expected):
    assert next_due(current, rule) == expected


def test_deleting_feature_keeps_task_unpinned(client, plot):
    task = make(client, plot, feature_id=plot["bed"])
    assert (
        client.delete(f"{plot['root']}/features/{plot['bed']}", headers=plot["owner"]).status_code
        == 204
    )
    kept = client.get(f"{plot['base']}/{task['id']}", headers=plot["owner"]).json
    assert kept["feature_id"] is None


def test_task_events_emitted(client, plot):
    seen = []
    events.subscribe("*", lambda e: seen.append(e.type))
    task = make(client, plot)
    client.post(f"{plot['base']}/{task['id']}/complete", headers=plot["editor"])
    client.post(f"{plot['base']}/{task['id']}/reopen", headers=plot["editor"])
    client.delete(f"{plot['base']}/{task['id']}", headers=plot["editor"])
    assert {"task.created", "task.completed", "task.reopened", "task.deleted"} <= set(seen)


def test_a_late_recurring_task_counts_from_today(client, plot):
    task = make(client, plot, due_date="2020-01-01", recurrence="daily")
    done = client.post(f"{plot['base']}/{task['id']}/complete", headers=plot["editor"]).json
    nxt = client.get(f"{plot['base']}/{done['spawned_task_id']}", headers=plot["editor"]).json
    assert nxt["due_date"] == (date.today() + timedelta(days=1)).isoformat()


def _tray_and_planting(client, plot):
    tray = client.post(
        f"{plot['root']}/trays",
        json={"name": "Spring", "rows": 2, "cols": 2},
        headers=plot["editor"],
    ).json["id"]
    return tray


def test_pin_to_a_tray_and_filter(client, plot):
    tray = _tray_and_planting(client, plot)
    pinned = make(client, plot, tray_id=tray, title="Check germination")
    make(client, plot, title="Something else")
    assert pinned["tray_id"] == tray and pinned["planting_id"] is None
    found = client.get(plot["base"], query_string={"tray_id": tray}, headers=plot["viewer"]).json
    assert [t["id"] for t in found] == [pinned["id"]]
    # a recurring task keeps its tray
    again = make(client, plot, tray_id=tray, recurrence="daily", due_date="2099-01-01")
    done = client.post(f"{plot['base']}/{again['id']}/complete", headers=plot["editor"]).json
    assert (
        client.get(f"{plot['base']}/{done['spawned_task_id']}", headers=plot["editor"]).json[
            "tray_id"
        ]
        == tray
    )


def test_tray_and_planting_must_belong_to_this_allotment(client, plot):
    other = client.post("/api/v1/allotments", json={"name": "Other"}, headers=plot["stranger"])
    tray = client.post(
        f"/api/v1/allotments/{other.json['id']}/trays",
        json={"name": "Not yours", "rows": 1, "cols": 1},
        headers=plot["stranger"],
    ).json["id"]
    resp = client.post(plot["base"], json={"title": "x", "tray_id": tray}, headers=plot["editor"])
    assert resp.status_code == 422
    resp = client.post(
        plot["base"], json={"title": "x", "planting_id": 99999}, headers=plot["editor"]
    )
    assert resp.status_code == 422


def test_search_and_priority_filters(client, plot):
    make(client, plot, title="Water the BEANS", priority="high")
    make(client, plot, title="Prune", description="the old beans row", priority="low")
    make(client, plot, title="Weed 100% of it")

    def titles(**q):
        return sorted(
            t["title"]
            for t in client.get(plot["base"], query_string=q, headers=plot["viewer"]).json
        )

    assert titles(q="beans") == ["Prune", "Water the BEANS"]
    assert titles(q="100%") == ["Weed 100% of it"]
    assert titles(q="_") == []
    assert titles(priority="high") == ["Water the BEANS"]
    assert (
        client.get(
            plot["base"], query_string={"priority": "urgent"}, headers=plot["viewer"]
        ).status_code
        == 422
    )


def bulk(client, plot, who="editor", **body):
    return client.post(f"{plot['base']}/bulk", json=body, headers=plot[who])


def test_bulk_complete_reopen_and_reschedule(client, plot):
    a = make(client, plot, title="A", recurrence="daily", due_date="2099-01-01")
    b = make(client, plot, title="B")
    done = bulk(client, plot, ids=[a["id"], b["id"]], action="complete")
    assert done.status_code == 200
    assert [t["status"] for t in done.json["tasks"]] == ["done", "done"]
    open_titles = [
        t["title"]
        for t in client.get(plot["base"], query_string={"open": True}, headers=plot["viewer"]).json
    ]
    assert open_titles == ["A"]  # the recurring one spawned its next occurrence
    reopened = bulk(client, plot, ids=[b["id"]], action="reopen")
    assert reopened.json["tasks"][0]["status"] == "todo"
    moved = bulk(client, plot, ids=[b["id"]], action="reschedule", due_date="2099-02-02")
    assert moved.json["tasks"][0]["due_date"] == "2099-02-02"
    cleared = bulk(client, plot, ids=[b["id"]], action="reschedule", due_date=None)
    assert cleared.json["tasks"][0]["due_date"] is None
    assert bulk(client, plot, ids=[b["id"]], action="reschedule").status_code == 422


def test_bulk_delete_and_all_or_nothing(client, plot):
    a = make(client, plot, title="A")
    b = make(client, plot, title="B")
    foreign = client.post("/api/v1/allotments", json={"name": "Other"}, headers=plot["stranger"])
    theirs = client.post(
        f"/api/v1/allotments/{foreign.json['id']}/tasks",
        json={"title": "Theirs"},
        headers=plot["stranger"],
    ).json["id"]
    refused = bulk(client, plot, ids=[a["id"], theirs], action="delete")
    assert refused.status_code == 404
    assert client.get(f"{plot['base']}/{a['id']}", headers=plot["viewer"]).status_code == 200
    ok = bulk(client, plot, ids=[a["id"], b["id"]], action="delete")
    assert ok.json["deleted"] == [a["id"], b["id"]]
    assert client.get(plot["base"], headers=plot["viewer"]).json == []


def test_bulk_needs_an_editor_and_records_events(client, plot):
    a = make(client, plot, title="A")
    assert bulk(client, plot, who="viewer", ids=[a["id"]], action="complete").status_code == 403
    assert bulk(client, plot, ids=[], action="complete").status_code == 422
    seen = []
    events.subscribe("*", lambda e: seen.append((e.type, e.subject.get("task_id"))))
    assert bulk(client, plot, ids=[a["id"]], action="complete").status_code == 200
    assert ("task.completed", a["id"]) in seen
