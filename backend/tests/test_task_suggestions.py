from datetime import date, timedelta

from allotment.task_suggestions import (
    Sowing,
    germination_date,
    harvest_date,
    plant_out_date,
    suggest_for_planting,
    suggest_for_tray,
)

from .test_media import plot  # noqa: F401 - owner, editor, viewer, stranger and a bed ("Bed 1")
from .test_plantings_api import INSIDE
from .test_trays import cells, packet, tray  # noqa: F401

SOWN = date(2026, 3, 1)


def sowing(**kw):
    return Sowing(packet_id=4, name="Tomato", sown_on=SOWN, **kw)


def due(suggestions):
    return {s.key.rsplit(":", 1)[1]: s.due_date for s in suggestions}


def test_dates_come_from_the_packet_or_a_default():
    assert germination_date(sowing()) == SOWN + timedelta(days=7)
    assert germination_date(sowing(germinate_days_min=10)) == SOWN + timedelta(days=10)


def test_planting_out_waits_for_the_calendar_month():
    s = sowing(germinate_days_min=7, plant_out_months=(5, 6))
    assert plant_out_date(s) == date(2026, 5, 1)  # ready on 5 April, but May is the first month
    ready_in_month = sowing(germinate_days_min=7, plant_out_months=(3, 4))
    assert plant_out_date(ready_in_month) == date(2026, 4, 5)  # germ 8 Mar + 28 days
    assert plant_out_date(sowing(germinate_days_min=7)) == date(
        2026, 4, 5
    )  # no calendar: when ready


def test_planting_out_can_roll_into_next_year():
    s = Sowing(packet_id=1, name="Kale", sown_on=date(2026, 11, 20), plant_out_months=(2, 3))
    assert plant_out_date(s) == date(2027, 2, 1)


def test_harvest_from_days_to_maturity_else_the_calendar():
    assert harvest_date(sowing(maturity_days_min=70), SOWN) == SOWN + timedelta(days=70)
    assert harvest_date(sowing(harvest_months=(8, 9)), date(2026, 5, 1)) == date(2026, 8, 1)
    assert harvest_date(sowing(), SOWN) is None


def test_a_tray_gets_each_step_in_date_order():
    s = sowing(germinate_days_min=7, maturity_days_min=90, plant_out_months=(5,))
    out = suggest_for_tray(12, "Spring tray", [s], today=SOWN)
    assert [x.key.rsplit(":", 1)[1] for x in out] == [
        "germination",
        "prick-out",
        "harden-off",
        "plant-out",
        "harvest",
    ]
    d = due(out)
    assert d["germination"] == date(2026, 3, 8)
    assert d["prick-out"] == date(2026, 3, 22)
    assert d["plant-out"] == date(2026, 5, 1) and d["harden-off"] == date(2026, 4, 24)
    assert d["harvest"] == date(2026, 5, 30)
    assert out[0].key == "tray:12:4:germination"
    assert "Tomato in Spring tray" in out[0].description and "1 Mar" in out[0].description


def test_steps_already_past_are_left_out_and_germinated_skips_the_check():
    s = sowing(germinate_days_min=7, plant_out_months=(5,))
    later = suggest_for_tray(1, "T", [s], today=date(2026, 4, 1))
    assert "germination" not in due(later) and "prick-out" not in due(later)
    assert "plant-out" in due(later)
    germinated = suggest_for_tray(1, "T", [sowing(germinated=True)], today=SOWN)
    assert "germination" not in due(germinated)


def test_each_kind_in_a_tray_has_its_own_keys():
    a = Sowing(packet_id=1, name="Leek", sown_on=SOWN)
    b = Sowing(packet_id=2, name="Beet", sown_on=SOWN)
    keys = [x.key for x in suggest_for_tray(3, "T", [a, b], today=SOWN)]
    assert len(keys) == len(set(keys)) and any(k.startswith("tray:3:1:") for k in keys)


def test_a_direct_sowing_gets_germination_thinning_and_harvest():
    s = sowing(germinate_days_min=10, maturity_days_min=80)
    out = suggest_for_planting(5, "Tomato in Bed 1", s, "direct_sow", "sown", False, SOWN)
    d = due(out)
    assert d == {
        "germination": date(2026, 3, 11),
        "thin": date(2026, 3, 25),
        "harvest": date(2026, 5, 20),
    }
    assert out[0].key == "planting:5:germination"


def test_a_transplanted_or_growing_planting_only_needs_harvesting():
    s = sowing(maturity_days_min=80)
    for method, status in (("transplant", "growing"), ("direct_sow", "growing")):
        out = suggest_for_planting(5, "x", s, method, status, False, SOWN)
        assert list(due(out)) == ["harvest"]


def test_nothing_for_a_finished_or_harvested_planting():
    s = sowing(maturity_days_min=80)
    assert suggest_for_planting(5, "x", s, "direct_sow", "finished", False, SOWN) == []
    assert suggest_for_planting(5, "x", s, "direct_sow", "failed", False, SOWN) == []
    assert suggest_for_planting(5, "x", s, "transplant", "harvesting", True, SOWN) == []


# --- the API ------------------------------------------------------------------------------------


def _sown_tray(client, plot, **packet_fields):  # noqa: F811
    today = date.today().isoformat()
    pid = packet(
        client,
        plot,
        name="Tomato",
        germinate_days_min=5,
        maturity_days_min=60,
        calendar={"plant_out": list(range(1, 13))},
        **packet_fields,
    )
    tid = tray(client, plot, sown_on=today).json["id"]
    assert (
        cells(client, plot, tid, [(0, 0), (0, 1)], packet_id=pid, status="sown").status_code == 200
    )
    return tid


def test_a_tray_previews_then_adds_its_tasks_once(client, plot):  # noqa: F811
    tid = _sown_tray(client, plot)
    url = f"{plot['base']}/trays/{tid}/suggested-tasks"
    preview = client.get(url, headers=plot["viewer"])
    assert preview.status_code == 200
    titles = [s["title"] for s in preview.json]
    assert titles[0] == "Check germination: Tomato" and "Plant out Tomato" in titles
    assert not any(s["added"] for s in preview.json)

    added = client.post(url, headers=plot["editor"])
    assert added.status_code == 201
    assert [t["title"] for t in added.json] == titles
    assert all(t["tray_id"] == tid for t in added.json)

    again = client.post(url, headers=plot["editor"])
    assert again.status_code == 201 and again.json == []  # nothing added twice
    assert all(s["added"] for s in client.get(url, headers=plot["viewer"]).json)
    listed = client.get(
        f"{plot['base']}/tasks", query_string={"tray_id": tid}, headers=plot["viewer"]
    )
    assert len(listed.json) == len(titles)


def test_only_an_editor_adds_suggested_tasks(client, plot):  # noqa: F811
    tid = _sown_tray(client, plot)
    url = f"{plot['base']}/trays/{tid}/suggested-tasks"
    assert client.post(url, headers=plot["viewer"]).status_code == 403
    assert client.post(url, headers=plot["stranger"]).status_code in (403, 404)
    assert client.get(url, headers=plot["stranger"]).status_code in (403, 404)
    assert (
        client.get(
            f"{plot['base']}/trays/99999/suggested-tasks", headers=plot["viewer"]
        ).status_code
        == 404
    )


def test_an_empty_tray_or_one_with_only_failed_seeds_suggests_nothing(client, plot):  # noqa: F811
    tid = tray(client, plot).json["id"]
    url = f"{plot['base']}/trays/{tid}/suggested-tasks"
    assert client.get(url, headers=plot["viewer"]).json == []
    pid = packet(client, plot)
    cells(client, plot, tid, [(0, 0)], packet_id=pid, status="failed")
    assert client.get(url, headers=plot["viewer"]).json == []


def test_a_planting_suggests_germination_thinning_and_harvest(client, plot):  # noqa: F811
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
    preview = client.get(url, headers=plot["viewer"]).json
    assert [s["title"] for s in preview] == [
        "Check germination: Carrot",
        "Thin Carrot",
        "Harvest Carrot",
    ]
    assert preview[0]["due_date"] == (date.today() + timedelta(days=8)).isoformat()
    added = client.post(url, headers=plot["editor"]).json
    assert [t["planting_id"] for t in added] == [sown["id"]] * 3
    assert client.post(url, headers=plot["editor"]).json == []


def test_deleting_the_tray_keeps_its_tasks(client, plot):  # noqa: F811
    tid = _sown_tray(client, plot)
    client.post(f"{plot['base']}/trays/{tid}/suggested-tasks", headers=plot["editor"])
    assert client.delete(f"{plot['base']}/trays/{tid}", headers=plot["editor"]).status_code == 204
    left = client.get(f"{plot['base']}/tasks", headers=plot["viewer"]).json
    assert any(t["title"] == "Check germination: Tomato" and t["tray_id"] is None for t in left)
