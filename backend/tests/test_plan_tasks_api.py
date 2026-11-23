from datetime import date, timedelta

from .test_media import plot  # noqa: F401 - owner, editor, viewer, stranger and a bed ("Bed 1")
from .test_plan import add, small_bed

TODAY = date.today()


def day(n):
    return (TODAY + timedelta(days=n)).isoformat()


def lettuce(client, plot, sow=10, end=80, **kw):  # noqa: F811
    return add(client, plot, sow_on=day(sow), end_on=day(end), **kw).json


def suggestions(client, plot, who="editor", query=""):  # noqa: F811
    resp = client.get(f"{plot['base']}/plan/task-suggestions{query}", headers=plot[who])
    assert resp.status_code == 200, resp.json
    return resp.json


def make(client, plot, who="editor", **body):  # noqa: F811
    return client.post(f"{plot['base']}/plan/tasks", json=body, headers=plot[who])


def sync(client, plot, **body):  # noqa: F811
    return client.post(f"{plot['base']}/plan/tasks/sync", json=body, headers=plot["editor"])


def plan_tasks_now(client, plot):  # noqa: F811
    rows = client.get(f"{plot['base']}/tasks", headers=plot["owner"]).json
    return sorted(
        (t for t in rows if t["plan_item_id"] is not None), key=lambda t: (t["due_date"], t["id"])
    )


def test_a_plan_item_suggests_a_sow_and_a_clear_task(client, plot):  # noqa: F811
    item = lettuce(client, plot)
    got = suggestions(client, plot, "viewer")
    assert got["stale"] == 0
    assert [(s["key"], s["added"]) for s in got["suggestions"]] == [
        (f"plan:sow:{item['id']}", False),
        (f"plan:change:{item['id']}:end", False),
    ]
    sow = got["suggestions"][0]
    assert (sow["title"], sow["due_date"], sow["feature_id"], sow["plan_item_id"]) == (
        "Sow Lettuce in Bed 1",
        day(10),
        plot["bed"],
        item["id"],
    )


def test_adding_makes_the_tasks_once(client, plot):  # noqa: F811
    item = lettuce(client, plot)
    made = make(client, plot)
    assert made.status_code == 201, made.json
    assert [t["title"] for t in made.json] == ["Sow Lettuce in Bed 1", "Clear Lettuce in Bed 1"]
    first = made.json[0]
    assert (first["feature_id"], first["plan_item_id"], first["due_date"], first["status"]) == (
        plot["bed"],
        item["id"],
        day(10),
        "todo",
    )
    assert make(client, plot).json == []  # nothing new the second time
    assert all(s["added"] for s in suggestions(client, plot)["suggestions"])
    assert len(plan_tasks_now(client, plot)) == 2


def test_adding_just_the_ones_named(client, plot):  # noqa: F811
    item = lettuce(client, plot)
    made = make(client, plot, keys=[f"plan:sow:{item['id']}"])
    assert [t["title"] for t in made.json] == ["Sow Lettuce in Bed 1"]
    rest = [s["key"] for s in suggestions(client, plot)["suggestions"] if not s["added"]]
    assert rest == [f"plan:change:{item['id']}:end"]
    unknown = make(client, plot, keys=["plan:sow:99999"])
    assert unknown.status_code == 422 and "plan:sow:99999" in unknown.json["message"]


def test_past_jobs_are_not_suggested_unless_asked_for(client, plot):  # noqa: F811
    item = add(client, plot, sow_on=day(-30), end_on=day(40)).json
    keys = [s["key"] for s in suggestions(client, plot)["suggestions"]]
    assert keys == [f"plan:change:{item['id']}:end"]  # the sowing date has passed
    assert make(client, plot).json[0]["title"].startswith("Clear")
    asked = make(client, plot, keys=[f"plan:sow:{item['id']}"])
    assert asked.status_code == 201 and asked.json[0]["due_date"] == day(-30)


def test_a_transplant_adds_a_plant_out_job(client, plot):  # noqa: F811
    item = add(
        client, plot, crop_key="tomato", method="transplant", sow_on=day(5),
        plant_out_on=day(50), end_on=day(150),
    ).json  # fmt: skip
    keys = [s["key"] for s in suggestions(client, plot)["suggestions"]]
    assert keys == [
        f"plan:sow:{item['id']}",
        f"plan:plant:{item['id']}",
        f"plan:change:{item['id']}:end",
    ]


def test_the_next_crop_is_named_in_the_changeover(client, plot):  # noqa: F811
    a = lettuce(client, plot, 10, 80)
    b = add(client, plot, crop_key="carrot", sow_on=day(85), end_on=day(200)).json
    clear = next(
        s for s in suggestions(client, plot)["suggestions"] if s["key"].startswith("plan:change:")
    )
    assert clear["key"] == f"plan:change:{a['id']}:{b['id']}"
    assert clear["title"] == "Clear Lettuce in Bed 1 and prepare for Carrot"


def test_editing_the_plan_makes_tasks_stale_and_sync_follows_it(client, plot):  # noqa: F811
    item = lettuce(client, plot)
    sow, clear = make(client, plot).json
    assert suggestions(client, plot)["stale"] == 0
    client.patch(
        f"{plot['base']}/plan-items/{item['id']}",
        json={"sow_on": day(20), "end_on": day(100), "name": "Little Gem"},
        headers=plot["editor"],
    )
    assert suggestions(client, plot)["stale"] == 2
    result = sync(client, plot)
    assert result.status_code == 200 and result.json == {"updated": 2, "removed": 0}
    now = {t["id"]: t for t in plan_tasks_now(client, plot)}
    assert (now[sow["id"]]["title"], now[sow["id"]]["due_date"]) == (
        "Sow Little Gem in Bed 1",
        day(20),
    )
    assert now[clear["id"]]["due_date"] == day(100)
    assert suggestions(client, plot)["stale"] == 0
    assert sync(client, plot).json == {"updated": 0, "removed": 0}


def test_sync_leaves_started_and_finished_tasks_alone(client, plot):  # noqa: F811
    item = lettuce(client, plot)
    sow, clear = make(client, plot).json
    client.post(f"{plot['base']}/tasks/{sow['id']}/complete", headers=plot["editor"])
    client.patch(
        f"{plot['base']}/tasks/{clear['id']}", json={"status": "doing"}, headers=plot["editor"]
    )
    client.patch(
        f"{plot['base']}/plan-items/{item['id']}",
        json={"sow_on": day(30), "end_on": day(120)},
        headers=plot["editor"],
    )
    assert suggestions(client, plot)["stale"] == 0  # nothing still to do differs
    assert sync(client, plot).json == {"updated": 0, "removed": 0}
    now = {t["id"]: t for t in plan_tasks_now(client, plot)}
    assert now[sow["id"]]["due_date"] == day(10) and now[sow["id"]]["status"] == "done"
    assert now[clear["id"]]["due_date"] == day(80) and now[clear["id"]]["status"] == "doing"


def test_skipping_or_finishing_an_item_removes_its_unstarted_tasks(client, plot):  # noqa: F811
    item = lettuce(client, plot)
    make(client, plot)
    client.patch(
        f"{plot['base']}/plan-items/{item['id']}",
        json={"status": "skipped"},
        headers=plot["editor"],
    )
    assert suggestions(client, plot)["stale"] == 2
    assert sync(client, plot).json == {"updated": 0, "removed": 2}
    assert plan_tasks_now(client, plot) == []
    assert suggestions(client, plot)["suggestions"] == []


def test_removing_the_next_crop_retargets_the_changeover(client, plot):  # noqa: F811
    a = lettuce(client, plot, 10, 80)
    b = add(client, plot, crop_key="carrot", sow_on=day(85), end_on=day(200)).json
    make(client, plot)
    client.delete(f"{plot['base']}/plan-items/{b['id']}", headers=plot["editor"])
    left = [t["title"] for t in plan_tasks_now(client, plot)]
    assert "Sow Carrot in Bed 1" not in left and "Clear Carrot in Bed 1" not in left  # went with it
    assert "Clear Lettuce in Bed 1 and prepare for Carrot" in left  # but this one is now wrong
    assert suggestions(client, plot)["stale"] == 1
    assert sync(client, plot).json == {"updated": 0, "removed": 1}
    fresh = [s for s in suggestions(client, plot)["suggestions"] if not s["added"]]
    assert [s["key"] for s in fresh] == [
        f"plan:change:{a['id']}:end"
    ]  # offered, not made behind your back


def test_deleting_an_item_keeps_the_tasks_already_done(client, plot):  # noqa: F811
    item = lettuce(client, plot)
    sow, clear = make(client, plot).json
    client.post(f"{plot['base']}/tasks/{sow['id']}/complete", headers=plot["editor"])
    client.delete(f"{plot['base']}/plan-items/{item['id']}", headers=plot["editor"])
    rows = {t["id"]: t for t in client.get(f"{plot['base']}/tasks", headers=plot["owner"]).json}
    assert clear["id"] not in rows  # not started: removed with the item
    assert rows[sow["id"]]["status"] == "done" and rows[sow["id"]]["plan_item_id"] is None


def test_a_bed_can_be_looked_at_on_its_own(client, plot):  # noqa: F811
    lettuce(client, plot)
    other = small_bed(client, plot, "Other")
    add(client, plot, feature_id=other, sow_on=day(12), end_on=day(60))
    both = suggestions(client, plot)["suggestions"]
    only = suggestions(client, plot, query=f"?feature_id={other}")["suggestions"]
    assert len(both) == 4 and len(only) == 2
    assert {s["feature_id"] for s in only} == {other}
    made = make(client, plot, feature_id=other)
    assert len(made.json) == 2 and {t["feature_id"] for t in made.json} == {other}
    assert len(suggestions(client, plot)["suggestions"]) == 4  # still listed, two now added


def test_roles(client, plot):  # noqa: F811
    lettuce(client, plot)
    assert make(client, plot, who="viewer").status_code == 403
    assert make(client, plot, who="stranger").status_code == 404
    assert (
        client.post(f"{plot['base']}/plan/tasks/sync", json={}, headers=plot["viewer"]).status_code
        == 403
    )
    assert (
        client.get(f"{plot['base']}/plan/task-suggestions", headers=plot["stranger"]).status_code
        == 404
    )
    assert (
        client.get(f"{plot['base']}/plan/task-suggestions", headers=plot["viewer"]).status_code
        == 200
    )


def test_plan_tasks_do_not_repeat_when_finished(client, plot):  # noqa: F811
    lettuce(client, plot)
    sow, _ = make(client, plot).json
    done = client.post(f"{plot['base']}/tasks/{sow['id']}/complete", headers=plot["editor"]).json
    assert done["spawned_task_id"] is None
