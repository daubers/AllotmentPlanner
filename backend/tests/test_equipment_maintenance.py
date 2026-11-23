from contextlib import contextmanager
from datetime import date, timedelta

from sqlalchemy import event

from allotment.extensions import db

from .test_equipment_api import add as add_equipment
from .test_media import plot  # noqa: F401 - owner, editor, viewer, stranger and a bed ("Bed 1")

TODAY = date.today()


def day(n):
    return (TODAY + timedelta(days=n)).isoformat()


def spade(client, plot, **kw):  # noqa: F811
    return add_equipment(client, plot, **kw).json["id"]


def schedule(client, plot, equipment_id, who="editor", **kw):  # noqa: F811
    body = {"starts_on": day(0), "until_on": day(90), "every_n": 1, "unit": "month", **kw}
    return client.post(
        f"{plot['base']}/equipment/{equipment_id}/maintenance", json=body, headers=plot[who]
    )


def maintenance_tasks(client, plot, equipment_id):  # noqa: F811
    rows = client.get(f"{plot['base']}/tasks", headers=plot["owner"]).json
    return sorted(
        (t for t in rows if t["equipment_id"] == equipment_id), key=lambda t: t["due_date"]
    )


def get(client, plot, equipment_id):  # noqa: F811
    return client.get(f"{plot['base']}/equipment/{equipment_id}", headers=plot["viewer"]).json


def test_scheduling_maintenance_makes_tasks_about_the_item(client, plot):  # noqa: F811
    a = spade(client, plot, name="Border spade")
    resp = schedule(client, plot, a, unit="week", until_on=day(21))
    assert resp.status_code == 201, resp.json
    s = resp.json
    assert (s["title"], s["equipment_id"], s["rule"], s["open_tasks"]) == (
        "Service Border spade",
        a,
        "every week",
        4,
    )
    tasks = maintenance_tasks(client, plot, a)
    assert [t["due_date"] for t in tasks] == [day(0), day(7), day(14), day(21)]
    first = tasks[0]
    assert (first["title"], first["series_id"], first["status"]) == (
        "Service Border spade",
        s["id"],
        "todo",
    )
    assert [e["name"] for e in first["equipment"]] == ["Border spade"]  # it shows its tool


def test_a_title_and_details_can_be_chosen(client, plot):  # noqa: F811
    a = spade(client, plot, name="Secateurs")
    s = schedule(
        client,
        plot,
        a,
        title="  Sharpen blades ",
        description="Use the stone",
        priority="high",
        every_n=3,
    ).json
    assert (s["title"], s["description"], s["priority"], s["rule"]) == (
        "Sharpen blades",
        "Use the stone",
        "high",
        "every 3 months",
    )
    first = maintenance_tasks(client, plot, a)[0]
    assert (first["priority"], first["description"]) == ("high", "Use the stone")


def test_a_single_job_is_a_schedule_that_ends_the_day_it_starts(client, plot):  # noqa: F811
    a = spade(client, plot)
    s = schedule(client, plot, a, starts_on=day(7), until_on=day(7), title="Oil the hinges").json
    assert s["open_tasks"] == 1
    assert [t["due_date"] for t in maintenance_tasks(client, plot, a)] == [day(7)]


def test_the_item_shows_when_it_is_next_due(client, plot):  # noqa: F811
    a = spade(client, plot)
    assert (get(client, plot, a)["next_due"], get(client, plot, a)["maintenance_tasks"]) == (
        None,
        0,
    )
    schedule(client, plot, a, starts_on=day(5), until_on=day(50))
    item = get(client, plot, a)
    assert (item["next_due"], item["overdue"], item["maintenance_tasks"]) == (day(5), False, 2)
    summary = client.get(f"{plot['base']}/equipment/{a}/maintenance", headers=plot["viewer"]).json
    assert (
        summary["next_due"] == day(5) and summary["open_tasks"] == 2 and summary["overdue"] is False
    )
    assert [s["equipment_id"] for s in summary["schedules"]] == [a]


def test_a_job_past_its_date_makes_the_item_overdue(client, plot):  # noqa: F811
    a = spade(client, plot)
    schedule(client, plot, a, starts_on=day(0), until_on=day(0))
    (job,) = maintenance_tasks(client, plot, a)
    client.patch(
        f"{plot['base']}/tasks/{job['id']}", json={"due_date": day(-3)}, headers=plot["editor"]
    )
    item = get(client, plot, a)
    assert (item["next_due"], item["overdue"]) == (day(-3), True)
    listed = client.get(f"{plot['base']}/equipment", headers=plot["viewer"]).json
    assert [(i["id"], i["overdue"]) for i in listed] == [(a, True)]


def test_doing_the_job_records_the_service(client, plot):  # noqa: F811
    a = spade(client, plot)
    schedule(client, plot, a, starts_on=day(0), until_on=day(30))
    assert get(client, plot, a)["last_serviced_on"] is None
    first = maintenance_tasks(client, plot, a)[0]
    client.post(f"{plot['base']}/tasks/{first['id']}/complete", headers=plot["editor"])
    item = get(client, plot, a)
    assert item["last_serviced_on"] == TODAY.isoformat()
    assert item["maintenance_tasks"] == 1  # the next one is still to do
    again = client.get(f"{plot['base']}/equipment/{a}/maintenance", headers=plot["viewer"]).json
    assert again["last_serviced_on"] == TODAY.isoformat()


def test_bulk_completion_records_it_too_and_never_goes_backwards(client, plot):  # noqa: F811
    a = spade(client, plot, last_serviced_on=day(60))  # recorded by hand as later than today
    b = spade(client, plot, name="Fork", kind="fork")
    for x in (a, b):
        schedule(client, plot, x, starts_on=day(0), until_on=day(0))
    ids = [maintenance_tasks(client, plot, x)[0]["id"] for x in (a, b)]
    client.post(
        f"{plot['base']}/tasks/bulk",
        json={"ids": ids, "action": "complete"},
        headers=plot["editor"],
    )
    assert get(client, plot, a)["last_serviced_on"] == day(60)  # unchanged
    assert get(client, plot, b)["last_serviced_on"] == TODAY.isoformat()


def test_the_last_service_can_be_recorded_by_hand(client, plot):  # noqa: F811
    a = spade(client, plot)
    resp = client.patch(
        f"{plot['base']}/equipment/{a}",
        json={"last_serviced_on": "2026-03-12"},
        headers=plot["editor"],
    )
    assert resp.status_code == 200 and resp.json["last_serviced_on"] == "2026-03-12"
    cleared = client.patch(
        f"{plot['base']}/equipment/{a}", json={"last_serviced_on": None}, headers=plot["editor"]
    )
    assert cleared.json["last_serviced_on"] is None


def test_changing_the_schedule_keeps_the_link(client, plot):  # noqa: F811
    a = spade(client, plot)
    s = schedule(client, plot, a, unit="week", until_on=day(21)).json
    resp = client.patch(
        f"{plot['base']}/task-series/{s['id']}", json={"every_n": 2}, headers=plot["editor"]
    )
    assert resp.status_code == 200 and resp.json["equipment_id"] == a
    tasks = maintenance_tasks(client, plot, a)
    assert [t["due_date"] for t in tasks] == [day(0), day(14)]
    assert all(t["equipment_id"] == a for t in tasks)


def test_a_maintenance_task_is_on_the_visits_bring_list(client, plot):  # noqa: F811
    a = spade(client, plot, name="Border spade")
    schedule(client, plot, a, starts_on=day(0), until_on=day(0))
    (job,) = maintenance_tasks(client, plot, a)
    v = client.post(
        f"{plot['base']}/visits",
        json={
            "title": "Service day",
            "starts_at": "2026-11-07T09:00:00+00:00",
            "task_ids": [job["id"]],
        },
        headers=plot["editor"],
    ).json
    assert [(b["name"], b["source"]) for b in v["bring"]] == [("Border spade", "task")]


def test_deleting_the_item_ends_its_maintenance(client, plot):  # noqa: F811
    a = spade(client, plot)
    s = schedule(client, plot, a, starts_on=day(0), until_on=day(90)).json
    done, started, *future = maintenance_tasks(client, plot, a)
    client.post(f"{plot['base']}/tasks/{done['id']}/complete", headers=plot["editor"])
    client.patch(
        f"{plot['base']}/tasks/{started['id']}", json={"status": "doing"}, headers=plot["editor"]
    )
    assert client.delete(f"{plot['base']}/equipment/{a}", headers=plot["editor"]).status_code == 204
    left = [
        t
        for t in client.get(f"{plot['base']}/tasks", headers=plot["owner"]).json
        if t["series_id"] in (s["id"], None) and t["title"] == s["title"]
    ]
    assert sorted(t["status"] for t in left) == ["doing", "done"]  # history and work in hand stay
    assert all(t["equipment_id"] is None and t["series_id"] is None for t in left)
    assert (
        client.get(f"{plot['base']}/task-series/{s['id']}", headers=plot["owner"]).status_code
        == 404
    )
    assert future and not [
        t
        for t in client.get(f"{plot['base']}/tasks", headers=plot["owner"]).json
        if t["status"] == "todo" and t["title"] == s["title"]
    ]


def test_bad_schedules_are_refused(client, plot, register):  # noqa: F811
    a = spade(client, plot)
    assert schedule(client, plot, a, starts_on=day(10), until_on=day(1)).status_code == 422
    assert schedule(client, plot, a, unit="day", until_on=day(400)).status_code == 422
    assert schedule(client, plot, a, unit="year").status_code == 422
    assert schedule(client, plot, a, assignee_id=999999).status_code == 422
    assert maintenance_tasks(client, plot, a) == []  # nothing half made
    other, _ = register("other@example.com", "Other")
    oid = client.post("/api/v1/allotments", json={"name": "Elsewhere"}, headers=other).json["id"]
    theirs = client.post(
        f"/api/v1/allotments/{oid}/equipment", json={"name": "Theirs"}, headers=other
    ).json["id"]
    assert schedule(client, plot, theirs).status_code == 404


def test_roles(client, plot):  # noqa: F811
    a = spade(client, plot)
    assert schedule(client, plot, a, who="viewer").status_code == 403
    assert schedule(client, plot, a, who="stranger").status_code == 404
    url = f"{plot['base']}/equipment/{a}/maintenance"
    assert client.get(url, headers=plot["viewer"]).status_code == 200
    assert client.get(url, headers=plot["stranger"]).status_code == 404


def test_the_equipment_list_does_not_cost_more_per_item(client, plot):  # noqa: F811
    first = spade(client, plot, name="Tool 0")
    schedule(client, plot, first)

    @contextmanager
    def counting():
        seen = []

        def count(conn, cursor, statement, *rest):
            if statement.lstrip().upper().startswith("SELECT"):
                seen.append(statement)

        event.listen(db.engine, "before_cursor_execute", count)
        try:
            yield seen
        finally:
            event.remove(db.engine, "before_cursor_execute", count)

    with counting() as few:
        client.get(f"{plot['base']}/equipment", headers=plot["viewer"])
    for i in range(1, 7):
        schedule(client, plot, spade(client, plot, name=f"Tool {i}"))
    with counting() as many:
        assert len(client.get(f"{plot['base']}/equipment", headers=plot["viewer"]).json) == 7
    assert len(many) == len(few), (len(few), len(many))
