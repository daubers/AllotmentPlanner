from datetime import UTC, datetime, timedelta

import pytest
from icalendar import Calendar

from allotment.extensions import db
from allotment.models import Task, VisitTask


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


def make_visit(client, plot, title="Saturday morning", **body):
    body.setdefault("starts_at", "2026-11-07T09:00:00+00:00")
    resp = client.post(
        f"{plot['base']}/visits", json={"title": title, **body}, headers=plot["owner"]
    )
    assert resp.status_code == 201, resp.json
    return resp.json


def url(plot, visit_id, tail=""):
    return f"{plot['base']}/visits/{visit_id}{tail}"


def test_create_with_tasks_and_defaults(client, plot):
    a, b = task(client, plot, "Water"), task(client, plot, "Weed")
    made = make_visit(client, plot, task_ids=[a, b, a])
    assert made["task_ids"] == [a, b]
    assert made["duration_minutes"] == 120
    assert made["notes"] == ""
    listing = client.get(f"{plot['base']}/visits", headers=plot["viewer"]).json
    assert [v["title"] for v in listing] == ["Saturday morning"]


def test_visits_are_soonest_first(client, plot):
    make_visit(client, plot, "Later", starts_at="2026-12-01T09:00:00+00:00")
    make_visit(client, plot, "Sooner", starts_at="2026-11-07T09:00:00+00:00")
    titles = [v["title"] for v in client.get(f"{plot['base']}/visits", headers=plot["owner"]).json]
    assert titles == ["Sooner", "Later"]


def test_roles(client, plot):
    made = make_visit(client, plot)
    assert client.get(url(plot, made["id"]), headers=plot["viewer"]).status_code == 200
    body = {"title": "x", "starts_at": "2026-11-07T09:00:00+00:00"}
    assert (
        client.post(f"{plot['base']}/visits", json=body, headers=plot["viewer"]).status_code == 403
    )
    assert (
        client.patch(url(plot, made["id"]), json={"title": "x"}, headers=plot["viewer"]).status_code
        == 403
    )
    assert client.delete(url(plot, made["id"]), headers=plot["viewer"]).status_code == 403
    add = {"task_ids": [1]}
    assert (
        client.post(url(plot, made["id"], "/tasks"), json=add, headers=plot["viewer"]).status_code
        == 403
    )
    assert client.get(f"{plot['base']}/visits", headers=plot["stranger"]).status_code == 404


def test_title_and_starts_at_are_required(client, plot):
    resp = client.post(f"{plot['base']}/visits", json={"title": ""}, headers=plot["owner"])
    assert resp.status_code == 422
    resp = client.post(
        f"{plot['base']}/visits",
        json={"starts_at": "2026-11-07T09:00:00+00:00"},
        headers=plot["owner"],
    )
    assert resp.status_code == 422


def test_add_is_idempotent_and_remove_leaves_the_task(client, plot):
    a, b = task(client, plot, "Water"), task(client, plot, "Weed")
    made = make_visit(client, plot, task_ids=[a])
    added = client.post(
        url(plot, made["id"], "/tasks"), json={"task_ids": [a, b]}, headers=plot["owner"]
    )
    assert added.json["task_ids"] == [a, b]
    again = client.post(
        url(plot, made["id"], "/tasks"), json={"task_ids": [b]}, headers=plot["owner"]
    )
    assert again.json["task_ids"] == [a, b]
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
    made = make_visit(client, plot)
    resp = client.post(
        url(plot, made["id"], "/tasks"), json={"task_ids": [mine, theirs]}, headers=plot["owner"]
    )
    assert resp.status_code == 422
    assert client.get(url(plot, made["id"]), headers=plot["owner"]).json["task_ids"] == []


def test_another_allotments_visit_is_not_found(client, plot, register):
    other_owner, _ = register("other@example.com", "Other")
    other = client.post("/api/v1/allotments", json={"name": "Elsewhere"}, headers=other_owner).json[
        "id"
    ]
    theirs = client.post(
        f"/api/v1/allotments/{other}/visits",
        json={"title": "Secret", "starts_at": "2026-11-07T09:00:00+00:00"},
        headers=other_owner,
    ).json
    assert client.get(url(plot, theirs["id"]), headers=plot["owner"]).status_code == 404


def test_deleting_a_visit_or_a_task_tidies_up_without_losing_the_other(client, plot):
    a, b = task(client, plot, "Water"), task(client, plot, "Weed")
    made = make_visit(client, plot, task_ids=[a, b])
    client.delete(f"{plot['base']}/tasks/{a}", headers=plot["owner"])
    assert client.get(url(plot, made["id"]), headers=plot["owner"]).json["task_ids"] == [b]
    assert client.delete(url(plot, made["id"]), headers=plot["owner"]).status_code == 204
    assert db.session.get(Task, b) is not None
    assert VisitTask.query.count() == 0


def test_patch_updates_fields_and_leaves_tasks_alone(client, plot):
    a = task(client, plot, "Water")
    made = make_visit(client, plot, "Old", task_ids=[a])
    resp = client.patch(
        url(plot, made["id"]),
        json={"title": " New ", "notes": "bring gloves", "duration_minutes": 45},
        headers=plot["owner"],
    )
    assert resp.status_code == 200
    assert (resp.json["title"], resp.json["notes"], resp.json["duration_minutes"]) == (
        "New",
        "bring gloves",
        45,
    )
    assert resp.json["task_ids"] == [a]


def test_single_visit_ics_has_a_stable_uid_and_the_task_checklist(client, plot):
    a, b = task(client, plot, "Water"), task(client, plot, "Weed")
    made = make_visit(
        client,
        plot,
        "Morning round",
        notes="bring gloves",
        task_ids=[a, b],
        starts_at="2026-11-07T09:00:00+00:00",
        duration_minutes=90,
    )
    resp = client.get(url(plot, made["id"], "/calendar.ics"), headers=plot["viewer"])
    assert resp.status_code == 200
    assert resp.mimetype == "text/calendar"
    cal = Calendar.from_ical(resp.data)
    (event,) = [c for c in cal.walk() if c.name == "VEVENT"]
    assert str(event["uid"]) == f"visit-{made['id']}@allotment.local"
    assert event["summary"] == "Morning round"
    assert "bring gloves" in str(event["description"])
    assert "Water" in str(event["description"]) and "Weed" in str(event["description"])
    start = event["dtstart"].dt
    end = event["dtend"].dt
    assert start.utcoffset() == timedelta(0)
    assert (end - start) == timedelta(minutes=90)
    (alarm,) = [c for c in event.walk() if c.name == "VALARM"]
    assert alarm["trigger"].dt == timedelta(hours=-1)

    again = client.get(url(plot, made["id"], "/calendar.ics"), headers=plot["viewer"])
    cal2 = Calendar.from_ical(again.data)
    (event2,) = [c for c in cal2.walk() if c.name == "VEVENT"]
    assert str(event2["uid"]) == str(event["uid"])


def test_editing_a_visit_bumps_the_ics_sequence(client, plot):
    made = make_visit(client, plot)
    resp = client.get(url(plot, made["id"], "/calendar.ics"), headers=plot["owner"])
    before = int(Calendar.from_ical(resp.data).walk("VEVENT")[0]["sequence"])
    client.patch(url(plot, made["id"]), json={"title": "Changed"}, headers=plot["owner"])
    resp = client.get(url(plot, made["id"], "/calendar.ics"), headers=plot["owner"])
    after = int(Calendar.from_ical(resp.data).walk("VEVENT")[0]["sequence"])
    assert after >= before


def test_calendar_ics_requires_membership(client, plot):
    made = make_visit(client, plot)
    assert client.get(
        url(plot, made["id"], "/calendar.ics"), headers=plot["stranger"]
    ).status_code == (404)


def test_calendar_token_create_rotate_and_disable(client, plot):
    assert client.get(f"{plot['base']}/visits/calendar-token", headers=plot["viewer"]).json == {
        "token": None,
        "feed_url": None,
    }
    assert (
        client.post(f"{plot['base']}/visits/calendar-token", headers=plot["viewer"]).status_code
        == 403
    )
    created = client.post(f"{plot['base']}/visits/calendar-token", headers=plot["owner"]).json
    assert created["token"]
    assert created["feed_url"].startswith("webcal://")
    assert created["token"] in created["feed_url"]

    rotated = client.post(f"{plot['base']}/visits/calendar-token", headers=plot["owner"]).json
    assert rotated["token"] != created["token"]

    old_feed = client.get(f"/api/v1/calendar/{created['token']}.ics")
    assert old_feed.status_code == 404
    new_feed = client.get(f"/api/v1/calendar/{rotated['token']}.ics")
    assert new_feed.status_code == 200

    disabled = client.delete(f"{plot['base']}/visits/calendar-token", headers=plot["owner"]).json
    assert disabled == {"token": None, "feed_url": None}
    assert client.get(f"/api/v1/calendar/{rotated['token']}.ics").status_code == 404


def test_feed_has_every_upcoming_visit_but_not_old_ones(client, plot):
    now = datetime.now(UTC)
    make_visit(client, plot, "Old", starts_at=(now - timedelta(days=90)).isoformat())
    make_visit(client, plot, "Upcoming", starts_at=(now + timedelta(days=1)).isoformat())
    token = client.post(f"{plot['base']}/visits/calendar-token", headers=plot["owner"]).json[
        "token"
    ]
    feed = client.get(f"/api/v1/calendar/{token}.ics")
    cal = Calendar.from_ical(feed.data)
    summaries = {str(e["summary"]) for e in cal.walk("VEVENT")}
    assert summaries == {"Upcoming"}


def test_feed_for_an_unknown_token_is_not_found(client, plot):
    assert client.get("/api/v1/calendar/does-not-exist.ics").status_code == 404
