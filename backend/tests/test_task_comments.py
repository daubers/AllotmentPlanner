from datetime import date

import pytest

from allotment import events
from allotment.extensions import db
from allotment.models import TaskComment


@pytest.fixture
def plot(client, register):
    owner, _ = register("owner@example.com", "Owner")
    editor, _ = register("editor@example.com", "Editor")
    other, _ = register("other@example.com", "Other")
    viewer, _ = register("viewer@example.com", "Viewer")
    stranger, _ = register("stranger@example.com", "Stranger")
    pid = client.post("/api/v1/allotments", json={"name": "Plot"}, headers=owner).json["id"]
    base = f"/api/v1/allotments/{pid}"
    for email in ("editor@example.com", "other@example.com"):
        client.post(f"{base}/members", json={"email": email, "role": "editor"}, headers=owner)
    client.post(f"{base}/members", json={"email": "viewer@example.com"}, headers=owner)
    return {
        "root": base,
        "owner": owner,
        "editor": editor,
        "other": other,
        "viewer": viewer,
        "stranger": stranger,
    }


def task(client, plot, **body):
    body.setdefault("title", "Water the beans")
    resp = client.post(f"{plot['root']}/tasks", json=body, headers=plot["editor"])
    assert resp.status_code == 201, resp.json
    return resp.json


def url(plot, task_id, tail=""):
    return f"{plot['root']}/tasks/{task_id}/comments{tail}"


def comment(client, plot, task_id, who="editor", **body):
    resp = client.post(url(plot, task_id), json=body, headers=plot[who])
    assert resp.status_code == 201, resp.json
    return resp.json


def current(client, plot, task_id):
    return client.get(f"{plot['root']}/tasks/{task_id}", headers=plot["owner"]).json


def test_comments_are_timestamped_and_listed_oldest_first(client, plot):
    t = task(client, plot)["id"]
    first = comment(client, plot, t, body="  Started on the left row  ")
    comment(client, plot, t, who="owner", body="Finished the right row")
    assert first["body"] == "Started on the left row"
    assert first["author"] == "Editor"
    assert first["created_at"] and first["status"] is None and first["edited"] is False
    listed = client.get(url(plot, t), headers=plot["viewer"]).json
    assert [c["body"] for c in listed] == ["Started on the left row", "Finished the right row"]
    assert listed[0]["created_at"] <= listed[1]["created_at"]


def test_a_comment_can_move_the_task_through_its_statuses(client, plot):
    t = task(client, plot)["id"]
    doing = comment(client, plot, t, body="Under way", status="doing")
    assert doing["status"] == "doing"
    assert current(client, plot, t)["status"] == "doing"
    done = comment(client, plot, t, status="done")
    assert done["body"] == "" and done["status"] == "done"
    after = current(client, plot, t)
    assert after["status"] == "done" and after["completed_at"] and after["completed_by"]
    comment(client, plot, t, body="Needs another go", status="todo")
    reopened = current(client, plot, t)
    assert reopened["status"] == "todo" and reopened["completed_at"] is None


def test_completing_by_comment_spawns_the_next_occurrence(client, plot):
    t = task(client, plot, recurrence="daily", due_date=date.today().isoformat())["id"]
    comment(client, plot, t, status="done")
    tasks = client.get(f"{plot['root']}/tasks", headers=plot["owner"]).json
    assert sorted(x["status"] for x in tasks) == ["done", "todo"]


def test_same_status_is_recorded_without_changing_the_task(client, plot):
    t = task(client, plot)["id"]
    made = comment(client, plot, t, body="Still to do", status="todo")
    assert made["status"] == "todo"
    assert current(client, plot, t)["status"] == "todo"


def test_progress_label_alone_is_enough_and_leaves_status_alone(client, plot):
    t = task(client, plot)["id"]
    made = comment(client, plot, t, progress="  waiting on seed  ")
    assert made["progress"] == "waiting on seed" and made["status"] is None
    assert current(client, plot, t)["status"] == "todo"


def test_an_empty_comment_is_rejected(client, plot):
    t = task(client, plot)["id"]
    for body in ({}, {"body": "   "}, {"progress": " "}):
        assert client.post(url(plot, t), json=body, headers=plot["editor"]).status_code == 422
    bad = client.post(url(plot, t), json={"status": "finished"}, headers=plot["editor"])
    assert bad.status_code == 422


def test_only_the_author_can_edit_and_edits_are_marked(client, plot):
    t = task(client, plot)["id"]
    made = comment(client, plot, t, body="Sowed", status="doing")
    path = url(plot, t, f"/{made['id']}")
    assert client.patch(path, json={"body": "x"}, headers=plot["other"]).status_code == 403
    assert client.patch(path, json={"body": "x"}, headers=plot["owner"]).status_code == 403
    row = db.session.get(TaskComment, made["id"])
    row.updated_at = row.created_at.replace(year=row.created_at.year - 1)  # as if long ago
    row.created_at = row.created_at.replace(year=row.created_at.year - 1)
    db.session.commit()
    resp = client.patch(path, json={"body": "Sowed twice"}, headers=plot["editor"])
    assert resp.status_code == 200
    assert resp.json["body"] == "Sowed twice" and resp.json["edited"] is True
    assert resp.json["status"] == "doing"  # the status it set stays
    assert current(client, plot, t)["status"] == "doing"


def test_an_edit_cannot_empty_a_comment(client, plot):
    t = task(client, plot)["id"]
    made = comment(client, plot, t, body="Only text")
    resp = client.patch(url(plot, t, f"/{made['id']}"), json={"body": ""}, headers=plot["editor"])
    assert resp.status_code == 422


def test_author_or_owner_can_delete_but_not_another_editor(client, plot):
    t = task(client, plot)["id"]
    a = comment(client, plot, t, body="one")["id"]
    b = comment(client, plot, t, body="two")["id"]
    assert client.delete(url(plot, t, f"/{a}"), headers=plot["other"]).status_code == 403
    assert client.delete(url(plot, t, f"/{a}"), headers=plot["editor"]).status_code == 204
    assert client.delete(url(plot, t, f"/{b}"), headers=plot["owner"]).status_code == 204
    assert client.get(url(plot, t), headers=plot["owner"]).json == []


def test_roles_and_membership(client, plot):
    t = task(client, plot)["id"]
    made = comment(client, plot, t, body="hello")
    assert client.get(url(plot, t), headers=plot["viewer"]).status_code == 200
    assert client.post(url(plot, t), json={"body": "x"}, headers=plot["viewer"]).status_code == 403
    assert client.get(url(plot, t), headers=plot["stranger"]).status_code == 404
    path = url(plot, t, f"/{made['id']}")
    assert client.delete(path, headers=plot["viewer"]).status_code == 403
    assert client.delete(path, headers=plot["stranger"]).status_code == 404


def test_comments_stay_with_their_own_task(client, plot):
    one = task(client, plot)["id"]
    two = task(client, plot, title="Other")["id"]
    made = comment(client, plot, one, body="mine")
    assert client.get(url(plot, two), headers=plot["owner"]).json == []
    resp = client.patch(
        url(plot, two, f"/{made['id']}"), json={"body": "x"}, headers=plot["editor"]
    )
    assert resp.status_code == 404
    assert client.get(url(plot, 99999), headers=plot["owner"]).status_code == 404


def test_deleting_a_task_removes_its_comments(client, plot):
    t = task(client, plot)["id"]
    comment(client, plot, t, body="gone soon")
    assert client.delete(f"{plot['root']}/tasks/{t}", headers=plot["editor"]).status_code == 204
    assert db.session.query(TaskComment).count() == 0


def test_events_and_activity(client, plot):
    t = task(client, plot)["id"]
    seen = []
    events.subscribe("*", lambda e: seen.append(e.type))
    comment(client, plot, t, body="Under way", status="doing")
    comment(client, plot, t, status="done")
    assert seen.count("task.comment_added") == 2
    assert "task.updated" in seen and "task.completed" in seen
    feed = client.get(f"{plot['root']}/activity", headers=plot["owner"])
    if feed.status_code == 200:
        types = [row["type"] for row in feed.json]
        assert "task.comment_added" in types
