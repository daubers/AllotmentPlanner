from datetime import date, timedelta

from .test_equipment_api import add as add_equipment
from .test_media import plot  # noqa: F401 - owner, editor, viewer, stranger and a bed ("Bed 1")
from .test_plan import add as add_item
from .test_task_suggestions import _sown_tray


def own(client, plot, name, kind):  # noqa: F811
    return add_equipment(client, plot, name=name, kind=kind).json["id"]


def by_segment(suggestions, segment):
    return next(s for s in suggestions if f":{segment}" in s["key"] or s["key"].endswith(segment))


def ids(s):
    return [e["id"] for e in s["equipment"]]


def test_tray_suggestions_name_the_equipment_you_own(client, plot):  # noqa: F811
    tray_tray = own(client, plot, "Module tray", "seed_tray")
    dibber = own(client, plot, "Steel dibber", "dibber")
    cloche = own(client, plot, "Glass cloche", "cloche")
    own(client, plot, "Hose", "hose")  # nothing here needs it
    tid = _sown_tray(client, plot)
    got = client.get(f"{plot['base']}/trays/{tid}/suggested-tasks", headers=plot["viewer"]).json
    assert ids(by_segment(got, "germination")) == [tray_tray]
    assert ids(by_segment(got, "prick-out")) == [dibber, tray_tray]
    assert ids(by_segment(got, "harden-off")) == [cloche]
    assert ids(by_segment(got, "plant-out")) == [dibber]  # no trowel owned
    first = by_segment(got, "germination")["equipment"][0]
    assert first["name"] == "Module tray" and first["reason"] == "germination"


def test_with_no_equipment_every_suggestion_has_an_empty_list(client, plot):  # noqa: F811
    tid = _sown_tray(client, plot)
    got = client.get(f"{plot['base']}/trays/{tid}/suggested-tasks", headers=plot["viewer"]).json
    assert got and all(s["equipment"] == [] for s in got)


def test_adding_attaches_only_the_equipment_you_ticked(client, plot):  # noqa: F811
    dibber = own(client, plot, "Dibber", "dibber")
    seed_tray = own(client, plot, "Tray", "seed_tray")
    tid = _sown_tray(client, plot)
    url = f"{plot['base']}/trays/{tid}/suggested-tasks"
    preview = client.get(url, headers=plot["viewer"]).json
    prick = by_segment(preview, "prick-out")["key"]
    germ = by_segment(preview, "germination")["key"]
    resp = client.post(url, json={"equipment": {prick: [dibber], germ: []}}, headers=plot["editor"])
    assert resp.status_code == 201, resp.json
    tasks = {t["suggestion_key"] if "suggestion_key" in t else t["title"]: t for t in resp.json}
    by_title = {t["title"]: t for t in resp.json}
    assert [e["id"] for e in by_title["Prick out Tomato if crowded"]["equipment"]] == [dibber]
    assert (
        by_title["Check germination: Tomato"]["equipment"] == []
    )  # suggested a tray, but not ticked
    assert seed_tray and tasks  # (the tray was only ever a suggestion)


def test_nothing_is_attached_unless_asked_for(client, plot):  # noqa: F811
    own(client, plot, "Dibber", "dibber")
    tid = _sown_tray(client, plot)
    added = client.post(f"{plot['base']}/trays/{tid}/suggested-tasks", headers=plot["editor"]).json
    assert added and all(t["equipment"] == [] for t in added)
    added_json = client.post(
        f"{plot['base']}/trays/{tid}/suggested-tasks", json={}, headers=plot["editor"]
    )
    assert (
        added_json.status_code == 201 and added_json.json == []
    )  # already added; an empty body is fine


def test_someone_elses_equipment_cannot_be_attached_and_no_tasks_are_made(client, plot, register):  # noqa: F811
    other, _ = register("other@example.com", "Other")
    oid = client.post("/api/v1/allotments", json={"name": "Elsewhere"}, headers=other).json["id"]
    theirs = client.post(
        f"/api/v1/allotments/{oid}/equipment", json={"name": "Theirs"}, headers=other
    ).json["id"]
    tid = _sown_tray(client, plot)
    url = f"{plot['base']}/trays/{tid}/suggested-tasks"
    key = client.get(url, headers=plot["viewer"]).json[0]["key"]
    resp = client.post(url, json={"equipment": {key: [theirs]}}, headers=plot["editor"])
    assert resp.status_code == 422
    assert all(not s["added"] for s in client.get(url, headers=plot["viewer"]).json)


def test_a_planting_suggests_a_hand_fork_to_thin(client, plot):  # noqa: F811
    from .test_plantings_api import INSIDE, packet

    fork = own(client, plot, "Hand fork", "hand_fork")
    pid = packet(client, plot, name="Carrot", germinate_days_min=8, maturity_days_min=70)
    sown = client.post(
        f"{plot['base']}/plantings",
        json={
            "feature_id": plot["bed"],
            "region": INSIDE,
            "packet_id": pid,
            "sown_on": date.today().isoformat(),
        },
        headers=plot["editor"],
    ).json
    url = f"{plot['base']}/plantings/{sown['id']}/suggested-tasks"
    thin = next(
        s for s in client.get(url, headers=plot["viewer"]).json if s["title"] == "Thin Carrot"
    )
    assert ids(thin) == [fork]
    added = client.post(url, json={"equipment": {thin["key"]: [fork]}}, headers=plot["editor"]).json
    assert [e["id"] for t in added if t["title"] == "Thin Carrot" for e in t["equipment"]] == [fork]


def _item(client, plot, **kw):  # noqa: F811
    soon = date.today() + timedelta(days=10)
    return add_item(
        client, plot, sow_on=soon.isoformat(), end_on=(soon + timedelta(days=60)).isoformat(), **kw
    ).json


def test_plan_tasks_suggest_equipment_and_attach_what_is_ticked(client, plot):  # noqa: F811
    dibber = own(client, plot, "Dibber", "dibber")
    labels = own(client, plot, "Labels", "plant_labels")
    fork = own(client, plot, "Fork", "fork")
    item = _item(client, plot)
    url = f"{plot['base']}/plan/task-suggestions"
    got = client.get(url, headers=plot["viewer"]).json["suggestions"]
    sow = next(s for s in got if s["key"] == f"plan:sow:{item['id']}")
    clear = next(s for s in got if s["key"].startswith("plan:change:"))
    assert ids(sow) == [dibber, labels] and ids(clear) == [fork]
    resp = client.post(
        f"{plot['base']}/plan/tasks",
        json={"equipment": {sow["key"]: [dibber]}},
        headers=plot["editor"],
    )
    assert resp.status_code == 201, resp.json
    made = {t["title"]: t for t in resp.json}
    assert [e["id"] for e in made["Sow Lettuce in Bed 1"]["equipment"]] == [dibber]
    assert made["Clear Lettuce in Bed 1"]["equipment"] == []  # a fork was suggested, not ticked


def test_plan_tasks_reject_someone_elses_equipment(client, plot, register):  # noqa: F811
    other, _ = register("other@example.com", "Other")
    oid = client.post("/api/v1/allotments", json={"name": "Elsewhere"}, headers=other).json["id"]
    theirs = client.post(
        f"/api/v1/allotments/{oid}/equipment", json={"name": "Theirs"}, headers=other
    ).json["id"]
    item = _item(client, plot)
    resp = client.post(
        f"{plot['base']}/plan/tasks",
        json={"equipment": {f"plan:sow:{item['id']}": [theirs]}},
        headers=plot["editor"],
    )
    assert resp.status_code == 422
    assert (
        client.get(f"{plot['base']}/tasks", headers=plot["viewer"]).json[0]["title"] == "Dig"
    )  # no new tasks
    again = client.get(f"{plot['base']}/plan/task-suggestions", headers=plot["viewer"]).json
    assert not any(s["added"] for s in again["suggestions"])
