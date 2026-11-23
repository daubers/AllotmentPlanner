from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

from icalendar import Calendar
from sqlalchemy import event

from allotment.extensions import db

from .test_equipment_api import add as add_equipment
from .test_media import plot  # noqa: F401 - owner, editor, viewer, stranger and a bed ("Bed 1")

WHEN = "2026-11-07T09:00:00+00:00"


def own(client, plot, name, kind=None, **kw):  # noqa: F811
    return add_equipment(client, plot, name=name, kind=kind, **kw).json["id"]


def task(client, plot, title, equipment=(), **kw):  # noqa: F811
    resp = client.post(
        f"{plot['base']}/tasks",
        json={"title": title, "equipment_ids": list(equipment), **kw},
        headers=plot["editor"],
    )
    assert resp.status_code == 201, resp.json
    return resp.json["id"]


def visit(client, plot, tasks=(), who="editor", **kw):  # noqa: F811
    body = {"title": "Saturday", "starts_at": WHEN, "task_ids": list(tasks), **kw}
    return client.post(f"{plot['base']}/visits", json=body, headers=plot[who])


def get(client, plot, visit_id, who="viewer"):  # noqa: F811
    return client.get(f"{plot['base']}/visits/{visit_id}", headers=plot[who]).json


def names(v):
    return [(b["name"], b["source"]) for b in v["bring"]]


def test_a_visit_brings_what_its_tasks_need(client, plot):  # noqa: F811
    spade = own(client, plot, "Border spade", "spade")
    fork = own(client, plot, "Garden fork", "fork")
    dig = task(client, plot, "Dig the bed", [spade, fork])
    water = task(client, plot, "Anything", [fork])
    v = visit(client, plot, [dig, water])
    assert v.status_code == 201, v.json
    assert names(v.json) == [("Border spade", "task"), ("Garden fork", "task")]
    by_name = {b["name"]: b for b in v.json["bring"]}
    assert by_name["Garden fork"]["task_ids"] == sorted([dig, water])
    assert by_name["Border spade"]["task_ids"] == [dig]
    assert (
        by_name["Border spade"]["kind_label"] == "Spade"
        and by_name["Border spade"]["quantity"] == 1
    )
    assert get(client, plot, v.json["id"])["bring"] == v.json["bring"]
    listed = client.get(f"{plot['base']}/visits", headers=plot["viewer"]).json
    assert listed[0]["bring"] == v.json["bring"]


def test_a_task_with_no_tools_suggests_some(client, plot):  # noqa: F811
    spade = own(client, plot, "Border spade", "spade")
    own(client, plot, "Dibber", "dibber")
    dig = task(client, plot, "Dig the bed")  # nothing ticked
    v = visit(client, plot, [dig]).json
    assert names(v) == [("Border spade", "suggested")]
    assert v["bring"][0]["id"] == spade and v["bring"][0]["task_ids"] == [dig]


def test_finished_tasks_need_nothing(client, plot):  # noqa: F811
    spade = own(client, plot, "Spade", "spade")
    done = task(client, plot, "Dig", [spade])
    client.post(f"{plot['base']}/tasks/{done}/complete", headers=plot["editor"])
    assert visit(client, plot, [done]).json["bring"] == []


def test_extras_and_removals(client, plot):  # noqa: F811
    spade = own(client, plot, "Spade", "spade")
    barrow = own(client, plot, "Wheelbarrow", "wheelbarrow")
    sieve = own(client, plot, "Sieve", "sieve")
    dig = task(client, plot, "Dig the bed", [spade])
    made = visit(client, plot, [dig], equipment_adds=[barrow], equipment_removes=[sieve]).json
    assert names(made) == [("Spade", "task"), ("Wheelbarrow", "extra")]
    assert sorted((e["equipment_id"], e["mode"]) for e in made["equipment_extras"]) == sorted(
        [(barrow, "add"), (sieve, "remove")]
    )
    url = f"{plot['base']}/visits/{made['id']}"
    hide = client.patch(
        url, json={"equipment_removes": [spade, sieve]}, headers=plot["editor"]
    ).json
    assert names(hide) == [("Wheelbarrow", "extra")]  # the spade is hidden; the added barrow stayed
    clear = client.patch(
        url, json={"equipment_adds": [], "equipment_removes": []}, headers=plot["editor"]
    ).json
    assert names(clear) == [("Spade", "task")] and clear["equipment_extras"] == []
    other = client.patch(url, json={"title": "Renamed"}, headers=plot["editor"]).json
    assert other["title"] == "Renamed"


def test_bad_extras_change_nothing(client, plot, register):  # noqa: F811
    spade = own(client, plot, "Spade", "spade")
    other, _ = register("other@example.com", "Other")
    oid = client.post("/api/v1/allotments", json={"name": "Elsewhere"}, headers=other).json["id"]
    theirs = client.post(
        f"/api/v1/allotments/{oid}/equipment", json={"name": "Theirs"}, headers=other
    ).json["id"]
    made = visit(client, plot, equipment_adds=[spade]).json
    url = f"{plot['base']}/visits/{made['id']}"
    both = client.patch(
        url, json={"equipment_adds": [spade], "equipment_removes": [spade]}, headers=plot["editor"]
    )
    assert both.status_code == 422 and "both added and removed" in both.json["message"]
    foreign = client.patch(url, json={"equipment_adds": [theirs]}, headers=plot["editor"])
    assert foreign.status_code == 422
    assert visit(client, plot, equipment_adds=[theirs]).status_code == 422
    assert names(get(client, plot, made["id"])) == [("Spade", "extra")]  # as it was


def test_deleting_equipment_takes_it_off_every_list(client, plot):  # noqa: F811
    spade = own(client, plot, "Spade", "spade")
    barrow = own(client, plot, "Barrow", "wheelbarrow")
    v = visit(client, plot, [task(client, plot, "Dig", [spade])], equipment_adds=[barrow]).json
    client.delete(f"{plot['base']}/equipment/{spade}", headers=plot["editor"])
    client.delete(f"{plot['base']}/equipment/{barrow}", headers=plot["editor"])
    assert get(client, plot, v["id"])["bring"] == []


def test_pegging_and_unpegging_change_the_list(client, plot):  # noqa: F811
    spade = own(client, plot, "Spade", "spade")
    dig = task(client, plot, "Dig", [spade])
    v = visit(client, plot).json
    assert v["bring"] == []
    pegged = client.post(
        f"{plot['base']}/visits/{v['id']}/tasks", json={"task_ids": [dig]}, headers=plot["editor"]
    ).json
    assert names(pegged) == [("Spade", "task")]
    gone = client.delete(
        f"{plot['base']}/visits/{v['id']}/tasks/{dig}", headers=plot["editor"]
    ).json
    assert gone["bring"] == []


def test_roles(client, plot):  # noqa: F811
    spade = own(client, plot, "Spade", "spade")
    v = visit(client, plot, [task(client, plot, "Dig", [spade])]).json
    url = f"{plot['base']}/visits/{v['id']}"
    assert names(client.get(url, headers=plot["viewer"]).json) == [("Spade", "task")]
    assert (
        client.patch(url, json={"equipment_adds": [spade]}, headers=plot["viewer"]).status_code
        == 403
    )
    assert (
        client.patch(url, json={"equipment_adds": [spade]}, headers=plot["stranger"]).status_code
        == 404
    )
    assert visit(client, plot, who="viewer").status_code == 403


# --- the calendar -------------------------------------------------------------------------------


def ics_event(client, plot, visit_id):  # noqa: F811
    resp = client.get(f"{plot['base']}/visits/{visit_id}/calendar.ics", headers=plot["viewer"])
    assert resp.status_code == 200
    (event,) = [c for c in Calendar.from_ical(resp.data).walk() if c.name == "VEVENT"]
    return event


def test_the_calendar_entry_lists_what_to_bring(client, plot):  # noqa: F811
    spade = own(client, plot, "Border spade", "spade")
    barrow = own(client, plot, "Wheelbarrow", "wheelbarrow")
    v = visit(
        client,
        plot,
        [task(client, plot, "Dig the bed", [spade])],
        notes="Be early",
        equipment_adds=[barrow],
    ).json
    description = str(ics_event(client, plot, v["id"])["description"])
    assert "Be early" in description and "- Dig the bed" in description
    assert description.endswith("Bring: Border spade, Wheelbarrow")


def test_a_visit_with_nothing_to_bring_has_no_bring_line(client, plot):  # noqa: F811
    v = visit(client, plot, [task(client, plot, "Think")]).json
    assert "Bring" not in str(ics_event(client, plot, v["id"])["description"])


def test_the_subscription_feed_lists_it_too(client, plot):  # noqa: F811
    spade = own(client, plot, "Border spade", "spade")
    v = visit(
        client,
        plot,
        [task(client, plot, "Dig the bed", [spade])],
        starts_at=(datetime.now(UTC) + timedelta(days=10)).isoformat(),
    ).json
    token = client.post(f"{plot['base']}/visits/calendar-token", headers=plot["editor"]).json[
        "token"
    ]
    resp = client.get(f"/api/v1/calendar/{token}.ics")
    (event,) = [c for c in Calendar.from_ical(resp.data).walk() if c.name == "VEVENT"]
    assert str(event["uid"]).startswith(f"visit-{v['id']}@")
    assert "Bring: Border spade" in str(event["description"])


def sequence(client, plot, visit_id):  # noqa: F811
    return int(ics_event(client, plot, visit_id)["sequence"])


def test_anything_that_changes_the_list_bumps_the_calendar_sequence(client, plot):  # noqa: F811
    import time

    spade = own(client, plot, "Spade", "spade")
    fork = own(client, plot, "Fork", "fork")
    dig = task(client, plot, "Dig", [spade])
    v = visit(client, plot, [dig]).json
    seen = [sequence(client, plot, v["id"])]

    def changed(why):
        time.sleep(1.1)  # the sequence counts whole seconds
        now = sequence(client, plot, v["id"])
        assert now > seen[-1], why
        seen.append(now)

    time.sleep(1.1)
    client.put(
        f"{plot['base']}/tasks/{dig}/equipment",
        json={"equipment_ids": [spade, fork]},
        headers=plot["editor"],
    )
    changed("a task's tools changed")
    client.patch(
        f"{plot['base']}/equipment/{fork}", json={"name": "Border fork"}, headers=plot["editor"]
    )
    changed("a tool was renamed")
    client.patch(
        f"{plot['base']}/visits/{v['id']}",
        json={"equipment_removes": [fork]},
        headers=plot["editor"],
    )
    changed("a tool was removed by hand")
    client.delete(f"{plot['base']}/equipment/{spade}", headers=plot["editor"])
    changed("a tool was deleted")


# --- cost -----------------------------------------------------------------------------------------


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


def test_listing_visits_costs_the_same_however_many_there_are(client, plot):  # noqa: F811
    tools = [own(client, plot, f"Tool {i}", "spade") for i in range(3)]
    one = visit(client, plot, [task(client, plot, "Dig 0", tools[:1])], title="One").json
    with counting() as few:
        assert len(client.get(f"{plot['base']}/visits", headers=plot["viewer"]).json) == 1
    for n in range(8):
        visit(
            client,
            plot,
            [task(client, plot, f"Dig {n}", tools[: n % 3 + 1]), task(client, plot, f"Hoe {n}")],
            title=f"V{n}",
        )
    with counting() as many:
        listed = client.get(f"{plot['base']}/visits", headers=plot["viewer"]).json
    assert len(listed) == 9 and one
    # a few more queries for the extra visits' tasks are fine; one per visit or task is not
    assert len(many) <= len(few) + 2, (len(few), len(many))


def test_the_export_includes_their_bring_list_changes(client, plot):  # noqa: F811
    import io
    import json
    import zipfile

    spade = own(client, plot, "Spade", "spade")
    visit(client, plot, equipment_adds=[spade])
    export = client.post("/api/v1/auth/me/export", headers=plot["editor"]).json
    for _ in range(3):
        if export.get("status") == "ready":
            break
        export = client.get(f"/api/v1/auth/me/export/{export['id']}", headers=plot["editor"]).json
    content = json.loads(
        zipfile.ZipFile(io.BytesIO(client.get(export["url"]).data)).read("data.json")
    )["content"]
    assert [(r["equipment_id"], r["mode"]) for r in content["visit_equipment"]] == [(spade, "add")]
