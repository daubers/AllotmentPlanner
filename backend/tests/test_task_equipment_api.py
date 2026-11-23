from contextlib import contextmanager

from sqlalchemy import event

from allotment.extensions import db

from .test_equipment_api import add as add_equipment
from .test_media import plot  # noqa: F401 - owner, editor, viewer, stranger and a bed ("Bed 1")


def task(client, plot, who="editor", **kw):  # noqa: F811
    body = {"title": "Dig the bed", **kw}
    return client.post(f"{plot['base']}/tasks", json=body, headers=plot[who])


def spade(client, plot, **kw):  # noqa: F811
    return add_equipment(client, plot, **kw).json["id"]


def names(t):
    return [e["name"] for e in t["equipment"]]


def test_a_task_can_be_made_with_equipment(client, plot):  # noqa: F811
    a, b = spade(client, plot, name="Spade"), spade(client, plot, name="Fork", kind="fork")
    resp = task(client, plot, equipment_ids=[b, a])
    assert resp.status_code == 201, resp.json
    assert names(resp.json) == ["Fork", "Spade"]  # by name
    first = resp.json["equipment"][1]
    assert first == {
        "id": a,
        "name": "Spade",
        "kind": "spade",
        "kind_label": "Spade",
        "quantity": 1,
        "status": "in_service",
    }
    assert task(client, plot).json["equipment"] == []  # none by default


def test_it_shows_wherever_tasks_do(client, plot):  # noqa: F811
    a = spade(client, plot)
    t = task(client, plot, equipment_ids=[a], due_date="2026-03-01").json
    base = plot["base"]
    assert names(client.get(f"{base}/tasks/{t['id']}", headers=plot["viewer"]).json) == ["Spade"]
    assert names(client.get(f"{base}/tasks", headers=plot["viewer"]).json[0]) == ["Spade"]
    todo = client.get(f"{base}/todo?date=2026-03-01", headers=plot["viewer"]).json
    assert names(todo["tasks"][0]) == ["Spade"]
    done = client.post(f"{base}/tasks/{t['id']}/complete", headers=plot["editor"]).json
    assert names(done) == ["Spade"]
    bulk = client.post(
        f"{base}/tasks/bulk", json={"ids": [t["id"]], "action": "reopen"}, headers=plot["editor"]
    )
    assert names(bulk.json["tasks"][0]) == ["Spade"]


def test_put_replaces_the_set(client, plot):  # noqa: F811
    a, b, c = (spade(client, plot, name=n) for n in ("A", "B", "C"))
    t = task(client, plot, equipment_ids=[a, b]).json
    url = f"{plot['base']}/tasks/{t['id']}/equipment"
    resp = client.put(url, json={"equipment_ids": [b, c]}, headers=plot["editor"])
    assert resp.status_code == 200 and names(resp.json) == ["B", "C"]
    assert names(
        client.put(url, json={"equipment_ids": [c, c, c]}, headers=plot["editor"]).json
    ) == ["C"]
    assert (
        client.put(url, json={"equipment_ids": []}, headers=plot["editor"]).json["equipment"] == []
    )


def test_patch_replaces_only_when_asked(client, plot):  # noqa: F811
    a = spade(client, plot)
    t = task(client, plot, equipment_ids=[a]).json
    url = f"{plot['base']}/tasks/{t['id']}"
    assert names(client.patch(url, json={"title": "Dig deeper"}, headers=plot["editor"]).json) == [
        "Spade"
    ]
    assert (
        client.patch(url, json={"equipment_ids": []}, headers=plot["editor"]).json["equipment"]
        == []
    )


def test_other_peoples_equipment_is_refused_and_nothing_changes(client, plot, register):  # noqa: F811
    mine = spade(client, plot)
    other, _ = register("other@example.com", "Other")
    oid = client.post("/api/v1/allotments", json={"name": "Elsewhere"}, headers=other).json["id"]
    theirs = client.post(
        f"/api/v1/allotments/{oid}/equipment", json={"name": "Theirs"}, headers=other
    ).json["id"]
    t = task(client, plot, equipment_ids=[mine]).json
    url = f"{plot['base']}/tasks/{t['id']}"
    for bad in ([theirs], [mine, 999999]):
        assert (
            client.put(
                f"{url}/equipment", json={"equipment_ids": bad}, headers=plot["editor"]
            ).status_code
            == 422
        )
        assert (
            client.patch(
                url, json={"title": "Changed", "equipment_ids": bad}, headers=plot["editor"]
            ).status_code
            == 422
        )
    assert task(client, plot, equipment_ids=[theirs]).status_code == 422
    after = client.get(url, headers=plot["editor"]).json
    assert (
        names(after) == ["Spade"] and after["title"] == "Dig the bed"
    )  # the refused edits left no trace
    titles = [x["title"] for x in client.get(f"{plot['base']}/tasks", headers=plot["editor"]).json]
    assert sorted(titles) == ["Dig", "Dig the bed"]  # the fixture's own task, and mine: no more


def test_equipment_and_task_deletes_are_independent(client, plot):  # noqa: F811
    a = spade(client, plot, name="A")
    b = spade(client, plot, name="B")
    t = task(client, plot, equipment_ids=[a, b]).json
    client.delete(f"{plot['base']}/equipment/{a}", headers=plot["editor"])
    assert names(client.get(f"{plot['base']}/tasks/{t['id']}", headers=plot["editor"]).json) == [
        "B"
    ]
    client.delete(f"{plot['base']}/tasks/{t['id']}", headers=plot["editor"])
    assert client.get(f"{plot['base']}/equipment/{b}", headers=plot["editor"]).status_code == 200


def test_out_of_action_equipment_stays_on_the_task_but_says_so(client, plot):  # noqa: F811
    a = spade(client, plot)
    t = task(client, plot, equipment_ids=[a]).json
    client.patch(
        f"{plot['base']}/equipment/{a}", json={"status": "out_of_action"}, headers=plot["editor"]
    )
    got = client.get(f"{plot['base']}/tasks/{t['id']}", headers=plot["viewer"]).json
    assert got["equipment"][0]["status"] == "out_of_action"


def test_roles(client, plot):  # noqa: F811
    a = spade(client, plot)
    t = task(client, plot).json
    url = f"{plot['base']}/tasks/{t['id']}/equipment"
    assert client.put(url, json={"equipment_ids": [a]}, headers=plot["viewer"]).status_code == 403
    assert client.put(url, json={"equipment_ids": [a]}, headers=plot["stranger"]).status_code == 404
    assert task(client, plot, who="viewer", equipment_ids=[a]).status_code == 403


@contextmanager
def counting(table):
    seen = []

    def count(conn, cursor, statement, *rest):
        if table in statement and statement.lstrip().upper().startswith("SELECT"):
            seen.append(statement)

    event.listen(db.engine, "before_cursor_execute", count)
    try:
        yield seen
    finally:
        event.remove(db.engine, "before_cursor_execute", count)


def test_listing_tasks_fetches_their_equipment_in_one_query(client, plot):  # noqa: F811
    ids = [spade(client, plot, name=f"Tool {i}") for i in range(3)]
    for i in range(12):
        task(client, plot, title=f"Job {i}", equipment_ids=ids[: i % 3 + 1], due_date="2026-03-01")
    with counting("task_equipment") as seen:
        assert len(client.get(f"{plot['base']}/tasks", headers=plot["viewer"]).json) == 13
    assert len(seen) == 1
    with counting("task_equipment") as seen:
        client.get(f"{plot['base']}/todo?date=2026-03-01", headers=plot["viewer"])
    assert len(seen) == 1


def test_the_export_includes_their_equipment_links(client, plot, register):  # noqa: F811
    import io
    import json
    import zipfile

    a = spade(client, plot)
    task(client, plot, equipment_ids=[a])
    export = client.post("/api/v1/auth/me/export", headers=plot["editor"]).json
    for _ in range(3):
        if export.get("status") == "ready":
            break
        export = client.get(f"/api/v1/auth/me/export/{export['id']}", headers=plot["editor"]).json
    zf = zipfile.ZipFile(io.BytesIO(client.get(export["url"]).data))
    content = json.loads(zf.read("data.json"))["content"]
    assert [r["equipment_id"] for r in content["task_equipment"]] == [a]


# --- suggesting -----------------------------------------------------------------------------------


def suggest(client, plot, who="viewer", **body):  # noqa: F811
    resp = client.post(f"{plot['base']}/equipment/suggest", json=body, headers=plot[who])
    assert resp.status_code == 200, resp.json
    return resp.json


def test_it_suggests_what_you_own_for_the_wording(client, plot):  # noqa: F811
    a = spade(client, plot, name="Border spade")
    spade(client, plot, name="Dibber", kind="dibber")
    got = suggest(client, plot, title="Dig the bed")
    assert [(s["id"], s["name"], s["reason"]) for s in got] == [(a, "Border spade", "digging")]
    assert got[0]["kind_label"] == "Spade" and got[0]["quantity"] == 1
    assert [s["name"] for s in suggest(client, plot, title="Sow the carrots")] == ["Dibber"]
    assert suggest(client, plot, title="Think about next year") == []


def test_your_own_words_come_first(client, plot):  # noqa: F811
    spade(client, plot, name="Border spade")
    odd = spade(client, plot, name="Trenching tool", kind=None, used_for="trench, dig")
    got = suggest(client, plot, title="Dig the bed")
    assert [s["id"] for s in got][0] == odd and got[0]["reason"] == "used for “dig”"


def test_it_leaves_out_out_of_action_and_excluded_items(client, plot):  # noqa: F811
    broken = spade(client, plot, name="Broken", status="out_of_action")
    ok = spade(client, plot, name="Good")
    spare = spade(client, plot, name="Spare")
    assert [s["id"] for s in suggest(client, plot, title="Dig")] == [ok, spare]
    assert [s["id"] for s in suggest(client, plot, title="Dig", exclude_ids=[ok])] == [spare]
    assert broken not in [s["id"] for s in suggest(client, plot, title="Dig")]


def test_a_generated_tasks_key_and_the_place_are_used(client, plot):  # noqa: F811
    dib = spade(client, plot, name="Dibber", kind="dibber")
    rake = spade(client, plot, name="Rake", kind="rake")
    assert [s["id"] for s in suggest(client, plot, title="Job", suggestion_key="plan:sow:4")] == [
        dib
    ]
    assert [s["id"] for s in suggest(client, plot, title="Job", feature_id=plot["bed"])] == [rake]
    assert (
        suggest(client, plot, title="Job", feature_id=999999) == []
    )  # an unknown place just adds nothing


def test_suggestions_only_ever_show_your_own_allotments_equipment(client, plot, register):  # noqa: F811
    spade(client, plot, name="Mine")
    other, _ = register("other@example.com", "Other")
    oid = client.post("/api/v1/allotments", json={"name": "Elsewhere"}, headers=other).json["id"]
    client.post(
        f"/api/v1/allotments/{oid}/equipment",
        json={"name": "Theirs", "kind": "spade"},
        headers=other,
    )
    assert [s["name"] for s in suggest(client, plot, title="Dig")] == ["Mine"]
    resp = client.post(
        f"{plot['base']}/equipment/suggest", json={"title": "Dig"}, headers=plot["stranger"]
    )
    assert resp.status_code == 404
