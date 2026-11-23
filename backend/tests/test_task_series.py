from datetime import date, timedelta

import pytest

from allotment import events
from allotment.api.tasks import next_due
from allotment.task_series import (
    MAX_OCCURRENCES,
    add_months,
    describe,
    occurrence_key,
    occurrences,
    step,
)

from .test_media import plot  # noqa: F401 - owner, editor, viewer, stranger and a bed ("Bed 1")

D = date


def test_step_units():
    assert step(D(2026, 3, 1), 3, "day") == D(2026, 3, 4)
    assert step(D(2026, 3, 1), 2, "week") == D(2026, 3, 15)
    assert step(D(2026, 3, 1), 2, "month") == D(2026, 5, 1)
    with pytest.raises(ValueError):
        step(D(2026, 3, 1), 1, "year")


def test_months_keep_the_day_or_use_the_last():
    assert add_months(D(2026, 1, 31), 1) == D(2026, 2, 28)
    assert add_months(D(2028, 1, 31), 1) == D(2028, 2, 29)
    assert add_months(D(2026, 11, 15), 3) == D(2027, 2, 15)
    assert add_months(D(2026, 1, 15), -2) == D(2025, 11, 15)
    assert add_months(D(2026, 12, 31), 12) == D(2027, 12, 31)


def test_the_old_recurrence_still_steps_the_same_way():
    assert next_due(D(2026, 3, 1), "daily") == D(2026, 3, 2)
    assert next_due(D(2026, 3, 1), "weekly") == D(2026, 3, 8)
    assert next_due(D(2026, 1, 31), "monthly") == D(2026, 2, 28)
    assert next_due(D(2026, 12, 15), "monthly") == D(2027, 1, 15)


def test_occurrences_include_both_ends():
    got = occurrences(D(2026, 3, 1), D(2026, 3, 15), 7, "day")
    assert got == [D(2026, 3, 1), D(2026, 3, 8), D(2026, 3, 15)]
    assert occurrences(D(2026, 3, 1), D(2026, 3, 14), 1, "week") == [D(2026, 3, 1), D(2026, 3, 8)]


def test_a_monthly_job_on_the_31st_goes_back_to_the_31st():
    got = occurrences(D(2026, 1, 31), D(2026, 5, 31), 1, "month")
    assert got == [D(2026, 1, 31), D(2026, 2, 28), D(2026, 3, 31), D(2026, 4, 30), D(2026, 5, 31)]


def test_not_before_drops_the_past_but_keeps_the_rhythm():
    got = occurrences(D(2026, 3, 1), D(2026, 3, 29), 1, "week", not_before=D(2026, 3, 10))
    assert got == [D(2026, 3, 15), D(2026, 3, 22), D(2026, 3, 29)]


def test_nothing_if_it_ends_before_it_starts():
    assert occurrences(D(2026, 3, 10), D(2026, 3, 1), 1, "day") == []


def test_the_cap():
    start = D(2026, 1, 1)
    assert len(occurrences(start, start + timedelta(days=MAX_OCCURRENCES - 1), 1, "day")) == 366
    with pytest.raises(ValueError, match="at most 366"):
        occurrences(start, start + timedelta(days=MAX_OCCURRENCES), 1, "day")
    # the cap counts past dates too, so it can't be sidestepped by filtering
    with pytest.raises(ValueError):
        occurrences(start, start + timedelta(days=500), 1, "day", not_before=D(2027, 6, 1))


def test_keys_and_wording():
    assert occurrence_key(12, D(2026, 3, 1)) == "series:12:2026-03-01"
    assert describe(1, "day") == "every day"
    assert describe(2, "week") == "every 2 weeks"
    assert describe(3, "month") == "every 3 months"


# --- the API -------------------------------------------------------------------------------------

TODAY = date.today()


def body(**kw):
    base = {
        "title": "Water the beans",
        "unit": "week",
        "every_n": 1,
        "starts_on": TODAY.isoformat(),
        "until_on": (TODAY + timedelta(days=28)).isoformat(),
    }
    return {**base, **kw}


def make(client, plot, who="editor", **kw):  # noqa: F811
    return client.post(f"{plot['base']}/task-series", json=body(**kw), headers=plot[who])


def tasks_of(client, plot, series_id):  # noqa: F811
    rows = client.get(f"{plot['base']}/tasks", headers=plot["owner"]).json
    return sorted((t for t in rows if t["series_id"] == series_id), key=lambda t: t["due_date"])


def test_a_series_creates_its_tasks_ahead(client, plot):  # noqa: F811
    resp = make(client, plot, description="at the base", priority="high", feature_id=plot["bed"])
    assert resp.status_code == 201, resp.json
    s = resp.json
    assert (s["rule"], s["open_tasks"], s["done_tasks"]) == ("every week", 5, 0)
    assert s["next_due"] == TODAY.isoformat()
    rows = tasks_of(client, plot, s["id"])
    assert [t["due_date"] for t in rows] == [
        (TODAY + timedelta(days=7 * i)).isoformat() for i in range(5)
    ]
    first = rows[0]
    assert (first["title"], first["description"], first["priority"]) == (
        "Water the beans",
        "at the base",
        "high",
    )
    assert (first["feature_id"], first["status"], first["recurrence"]) == (
        plot["bed"],
        "todo",
        None,
    )


def test_completing_an_occurrence_does_not_spawn_another(client, plot):  # noqa: F811
    s = make(client, plot).json
    first = tasks_of(client, plot, s["id"])[0]
    done = client.post(f"{plot['base']}/tasks/{first['id']}/complete", headers=plot["editor"]).json
    assert done["spawned_task_id"] is None
    assert len(tasks_of(client, plot, s["id"])) == 5
    got = client.get(f"{plot['base']}/task-series/{s['id']}", headers=plot["viewer"]).json
    assert (got["open_tasks"], got["done_tasks"]) == (4, 1)


def test_dates_in_the_past_are_not_created(client, plot):  # noqa: F811
    # every 3 days from 10 days ago: -10, -7, -4, -1, +2, +5. Only the last two are still to come.
    s = make(
        client,
        plot,
        starts_on=(TODAY - timedelta(days=10)).isoformat(),
        unit="day",
        every_n=3,
        until_on=(TODAY + timedelta(days=6)).isoformat(),
    ).json
    due = [t["due_date"] for t in tasks_of(client, plot, s["id"])]
    assert due == [(TODAY + timedelta(days=2)).isoformat(), (TODAY + timedelta(days=5)).isoformat()]


def test_changing_the_rule_remakes_what_is_still_to_come(client, plot):  # noqa: F811
    s = make(client, plot).json  # weekly for 4 weeks: 5 tasks
    rows = tasks_of(client, plot, s["id"])
    client.post(f"{plot['base']}/tasks/{rows[0]['id']}/complete", headers=plot["editor"])
    client.patch(
        f"{plot['base']}/tasks/{rows[1]['id']}", json={"status": "doing"}, headers=plot["editor"]
    )
    resp = client.patch(
        f"{plot['base']}/task-series/{s['id']}",
        json={"every_n": 2, "title": "Water well"},
        headers=plot["editor"],
    )
    assert resp.status_code == 200, resp.json
    assert resp.json["rule"] == "every 2 weeks"
    now = tasks_of(client, plot, s["id"])
    by_date = {t["due_date"]: t for t in now}
    # the finished one and the one being worked on are untouched, with their old title
    assert (
        by_date[rows[0]["due_date"]]["status"] == "done"
        and by_date[rows[0]["due_date"]]["title"] == "Water the beans"
    )
    assert (
        by_date[rows[1]["due_date"]]["status"] == "doing"
        and by_date[rows[1]["due_date"]]["title"] == "Water the beans"
    )
    # the rest follow the new rhythm (day 0, 14, 28), and carry the new title
    assert (TODAY + timedelta(days=14)).isoformat() in by_date
    assert (TODAY + timedelta(days=21)).isoformat() not in by_date
    assert by_date[(TODAY + timedelta(days=14)).isoformat()]["title"] == "Water well"
    keys = [t["id"] for t in now]
    assert len(keys) == len(set(keys))


def test_a_bad_change_leaves_everything_as_it_was(client, plot):  # noqa: F811
    s = make(client, plot).json
    before = tasks_of(client, plot, s["id"])
    bad = client.patch(
        f"{plot['base']}/task-series/{s['id']}",
        json={"until_on": (TODAY - timedelta(days=1)).isoformat()},
        headers=plot["editor"],
    )
    assert bad.status_code == 422 and "ends before" in bad.json["message"]
    too_long = client.patch(
        f"{plot['base']}/task-series/{s['id']}",
        json={"unit": "day", "until_on": (TODAY + timedelta(days=400)).isoformat()},
        headers=plot["editor"],
    )
    assert too_long.status_code == 422 and "366" in too_long.json["message"]
    assert tasks_of(client, plot, s["id"]) == before
    got = client.get(f"{plot['base']}/task-series/{s['id']}", headers=plot["viewer"]).json
    assert got["unit"] == "week"  # the refused edit was not kept


def test_stopping_a_series_removes_only_what_has_not_started(client, plot):  # noqa: F811
    s = make(client, plot).json
    rows = tasks_of(client, plot, s["id"])
    client.post(f"{plot['base']}/tasks/{rows[0]['id']}/complete", headers=plot["editor"])
    assert (
        client.delete(f"{plot['base']}/task-series/{s['id']}", headers=plot["editor"]).status_code
        == 204
    )
    left = [
        t
        for t in client.get(f"{plot['base']}/tasks", headers=plot["owner"]).json
        if t["title"] == "Water the beans"
    ]
    assert [(t["id"], t["status"], t["series_id"]) for t in left] == [(rows[0]["id"], "done", None)]
    assert (
        client.get(f"{plot['base']}/task-series/{s['id']}", headers=plot["owner"]).status_code
        == 404
    )


def test_validation(client, plot, register):  # noqa: F811
    assert make(client, plot, unit="year").status_code == 422
    assert make(client, plot, every_n=0).status_code == 422
    assert make(client, plot, until_on=(TODAY - timedelta(days=1)).isoformat()).status_code == 422
    assert (
        make(
            client, plot, unit="day", until_on=(TODAY + timedelta(days=400)).isoformat()
        ).status_code
        == 422
    )
    assert make(client, plot, feature_id=999999).status_code == 422
    assert make(client, plot, assignee_id=999999).status_code == 422
    other, _ = register("other@example.com", "Other")
    oid = client.post("/api/v1/allotments", json={"name": "Elsewhere"}, headers=other).json["id"]
    foreign = client.post(
        f"/api/v1/allotments/{oid}/features",
        json={
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [0, 0]},
            "properties": {"kind": "bed"},
        },
        headers=other,
    ).json["id"]
    assert make(client, plot, feature_id=foreign).status_code == 422


def test_roles_and_isolation(client, plot, register):  # noqa: F811
    assert make(client, plot, who="viewer").status_code == 403
    assert make(client, plot, who="stranger").status_code == 404
    s = make(client, plot).json
    base = f"{plot['base']}/task-series/{s['id']}"
    assert client.get(base, headers=plot["viewer"]).status_code == 200
    assert (
        client.get(f"{plot['base']}/task-series", headers=plot["viewer"]).json[0]["id"] == s["id"]
    )
    assert client.patch(base, json={"title": "x"}, headers=plot["viewer"]).status_code == 403
    assert client.delete(base, headers=plot["viewer"]).status_code == 403
    assert client.get(base, headers=plot["stranger"]).status_code == 404
    other, _ = register("other@example.com", "Other")
    oid = client.post("/api/v1/allotments", json={"name": "Elsewhere"}, headers=other).json["id"]
    assert (
        client.get(f"/api/v1/allotments/{oid}/task-series/{s['id']}", headers=other).status_code
        == 404
    )


def test_deleting_the_allotment_or_task_does_not_trip_the_series(client, plot):  # noqa: F811
    s = make(client, plot).json
    first = tasks_of(client, plot, s["id"])[0]
    assert (
        client.delete(f"{plot['base']}/tasks/{first['id']}", headers=plot["editor"]).status_code
        == 204
    )
    got = client.get(f"{plot['base']}/task-series/{s['id']}", headers=plot["owner"]).json
    assert got["open_tasks"] == 4


def test_events_are_emitted(client, plot):  # noqa: F811
    seen = []
    events.subscribe(events.WILDCARD, lambda e: seen.append(e.type))
    s = make(client, plot).json
    client.patch(
        f"{plot['base']}/task-series/{s['id']}", json={"title": "x"}, headers=plot["editor"]
    )
    client.delete(f"{plot['base']}/task-series/{s['id']}", headers=plot["editor"])
    assert [t for t in seen if t.startswith("task_series.")] == [
        "task_series.created",
        "task_series.updated",
        "task_series.deleted",
    ]
