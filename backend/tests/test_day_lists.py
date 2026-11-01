import pytest

from allotment.extensions import db
from allotment.models import DayListItem, Task


@pytest.fixture
def plot(client, register):
    owner, _ = register("owner@example.com", "Owner")
    viewer, _ = register("viewer@example.com", "Viewer")
    stranger, _ = register("stranger@example.com", "Stranger")
    pid = client.post("/api/v1/allotments", json={"name": "Plot 12"}, headers=owner).json["id"]
    base = f"/api/v1/allotments/{pid}"
    client.post(f"{base}/members", json={"email": "viewer@example.com"}, headers=owner)
    return {"base": base, "owner": owner, "viewer": viewer, "stranger": stranger}


def task(client, plot, title, **body):
    resp = client.post(
        f"{plot['base']}/tasks", json={"title": title, **body}, headers=plot["owner"]
    )
    assert resp.status_code == 201, resp.json
    return resp.json["id"]


def make_list(client, plot, name="Saturday", **body):
    resp = client.post(
        f"{plot['base']}/day-lists", json={"name": name, **body}, headers=plot["owner"]
    )
    assert resp.status_code == 201, resp.json
    return resp.json


def url(plot, list_id, tail=""):
    return f"{plot['base']}/day-lists/{list_id}{tail}"


def test_create_with_tasks_and_list(client, plot):
    a, b = task(client, plot, "Water"), task(client, plot, "Weed")
    made = make_list(client, plot, "Saturday", date="2026-11-07", task_ids=[a, b, a])
    assert made["task_ids"] == [a, b]
    assert (made["task_count"], made["done_count"], made["date"]) == (2, 0, "2026-11-07")
    listing = client.get(f"{plot['base']}/day-lists", headers=plot["viewer"]).json
    assert [d["name"] for d in listing] == ["Saturday"]


def test_lists_are_newest_first_and_several_can_share_a_date(client, plot):
    make_list(client, plot, "Morning", date="2026-11-07")
    make_list(client, plot, "Evening", date="2026-11-07")
    names = [d["name"] for d in client.get(f"{plot['base']}/day-lists", headers=plot["owner"]).json]
    assert names == ["Evening", "Morning"]


def test_roles(client, plot):
    made = make_list(client, plot)
    assert client.get(url(plot, made["id"]), headers=plot["viewer"]).status_code == 200
    body = {"name": "x"}
    assert (
        client.post(f"{plot['base']}/day-lists", json=body, headers=plot["viewer"]).status_code
        == 403
    )
    assert client.patch(url(plot, made["id"]), json=body, headers=plot["viewer"]).status_code == 403
    assert client.delete(url(plot, made["id"]), headers=plot["viewer"]).status_code == 403
    add = {"task_ids": [1]}
    assert (
        client.post(url(plot, made["id"], "/tasks"), json=add, headers=plot["viewer"]).status_code
        == 403
    )
    assert client.get(f"{plot['base']}/day-lists", headers=plot["stranger"]).status_code == 404
    assert client.get(url(plot, made["id"], "/todo"), headers=plot["stranger"]).status_code == 404


def test_name_is_required(client, plot):
    resp = client.post(f"{plot['base']}/day-lists", json={"name": ""}, headers=plot["owner"])
    assert resp.status_code == 422


def test_add_is_idempotent_and_remove_leaves_the_task(client, plot):
    a, b = task(client, plot, "Water"), task(client, plot, "Weed")
    made = make_list(client, plot, task_ids=[a])
    added = client.post(
        url(plot, made["id"], "/tasks"), json={"task_ids": [a, b]}, headers=plot["owner"]
    )
    assert added.json["task_ids"] == [a, b]
    again = client.post(
        url(plot, made["id"], "/tasks"), json={"task_ids": [b]}, headers=plot["owner"]
    )
    assert again.json["task_count"] == 2
    gone = client.delete(url(plot, made["id"], f"/tasks/{a}"), headers=plot["owner"])
    assert gone.json["task_ids"] == [b]
    assert db.session.get(Task, a) is not None
    missing = client.delete(url(plot, made["id"], f"/tasks/{a}"), headers=plot["owner"])
    assert missing.status_code == 404


def test_a_task_from_another_allotment_is_refused_and_nothing_is_added(client, plot, register):
    mine = task(client, plot, "Mine")
    other_owner, _ = register("other@example.com", "Other")
    other = client.post("/api/v1/allotments", json={"name": "Elsewhere"}, headers=other_owner).json[
        "id"
    ]
    theirs = client.post(
        f"/api/v1/allotments/{other}/tasks", json={"title": "Theirs"}, headers=other_owner
    ).json["id"]
    made = make_list(client, plot)
    resp = client.post(
        url(plot, made["id"], "/tasks"), json={"task_ids": [mine, theirs]}, headers=plot["owner"]
    )
    assert resp.status_code == 422
    assert client.get(url(plot, made["id"]), headers=plot["owner"]).json["task_count"] == 0
    bad = client.post(
        f"{plot['base']}/day-lists", json={"name": "N", "task_ids": [theirs]}, headers=plot["owner"]
    )
    assert bad.status_code == 422


def test_rename_and_clear_the_date(client, plot):
    made = make_list(client, plot, "Old", date="2026-11-07")
    resp = client.patch(
        url(plot, made["id"]), json={"name": " New ", "date": None}, headers=plot["owner"]
    )
    assert (resp.json["name"], resp.json["date"]) == ("New", None)


def test_another_allotments_list_is_not_found(client, plot, register):
    other_owner, _ = register("other@example.com", "Other")
    other = client.post("/api/v1/allotments", json={"name": "Elsewhere"}, headers=other_owner).json[
        "id"
    ]
    theirs = client.post(
        f"/api/v1/allotments/{other}/day-lists", json={"name": "Secret"}, headers=other_owner
    ).json
    assert client.get(url(plot, theirs["id"]), headers=plot["owner"]).status_code == 404


def test_deleting_a_list_or_a_task_tidies_up_without_losing_the_other(client, plot):
    a, b = task(client, plot, "Water"), task(client, plot, "Weed")
    made = make_list(client, plot, task_ids=[a, b])
    client.delete(f"{plot['base']}/tasks/{a}", headers=plot["owner"])
    assert client.get(url(plot, made["id"]), headers=plot["owner"]).json["task_ids"] == [b]
    assert client.delete(url(plot, made["id"]), headers=plot["owner"]).status_code == 204
    assert db.session.get(Task, b) is not None
    assert DayListItem.query.count() == 0


def test_the_sheet_has_the_lists_tasks_with_done_ones_kept_and_last(client, plot):
    low = task(client, plot, "Low", priority="low")
    high = task(client, plot, "High", priority="high")
    done = task(client, plot, "Finished", priority="high")
    task(client, plot, "Not on the list")
    client.post(f"{plot['base']}/tasks/{done}/complete", headers=plot["owner"])
    made = make_list(client, plot, "Round", date="2026-11-07", task_ids=[low, done, high])
    sheet = client.get(url(plot, made["id"], "/todo"), headers=plot["viewer"]).json
    assert [t["title"] for t in sheet["tasks"]] == ["High", "Low", "Finished"]
    assert sheet["title"] == "Round"
    assert sheet["date"] == "2026-11-07"
    assert sheet["allotment"]["name"] == "Plot 12"
    assert sheet["members"]


def test_an_empty_list_has_an_empty_sheet(client, plot):
    made = make_list(client, plot)
    sheet = client.get(url(plot, made["id"], "/todo"), headers=plot["owner"]).json
    assert sheet["tasks"] == []
    assert sheet["date"]
