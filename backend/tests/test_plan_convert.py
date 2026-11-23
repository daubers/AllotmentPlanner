from datetime import date, timedelta

import pytest

from .test_media import plot  # noqa: F401 - owner, editor, viewer, stranger and a bed ("Bed 1")
from .test_plan import add, small_bed
from .test_plantings_api import INSIDE, sow

TODAY = date.today()


def planned(client, plot, **kw):  # noqa: F811
    kw.setdefault("sow_on", (TODAY + timedelta(days=5)).isoformat())
    kw.setdefault("end_on", (TODAY + timedelta(days=60)).isoformat())
    return add(client, plot, **kw).json


def item_now(client, plot, item_id):  # noqa: F811
    return client.get(f"{plot['base']}/plan-items/{item_id}", headers=plot["owner"]).json


def test_planting_a_plan_item_marks_it_done_and_links_the_planting(client, plot):  # noqa: F811
    item = planned(client, plot)
    resp = sow(client, plot, INSIDE, count=30, plan_item_id=item["id"])
    assert resp.status_code == 201, resp.json
    now = item_now(client, plot, item["id"])
    assert (now["status"], now["planting_id"]) == ("done", resp.json["id"])


def test_a_planting_without_a_plan_item_is_unchanged(client, plot):  # noqa: F811
    item = planned(client, plot)
    assert sow(client, plot, INSIDE).status_code == 201
    assert item_now(client, plot, item["id"])["status"] == "planned"


def test_the_item_must_be_for_this_bed(client, plot):  # noqa: F811
    other = small_bed(client, plot, "Other")
    item = planned(client, plot, feature_id=other)
    resp = sow(client, plot, INSIDE, plan_item_id=item["id"])
    assert resp.status_code == 422 and "different bed" in resp.json["message"]
    assert item_now(client, plot, item["id"])["status"] == "planned"
    assert (
        client.get(f"{plot['base']}/plantings", headers=plot["owner"]).json == []
    )  # nothing saved


def test_an_item_from_another_allotment_is_refused(client, plot, register):  # noqa: F811
    other, _ = register("other@example.com", "Other")
    oid = client.post("/api/v1/allotments", json={"name": "Elsewhere"}, headers=other).json["id"]
    assert sow(client, plot, INSIDE, plan_item_id=424242).status_code == 422
    # an item that exists, but in someone else's allotment
    bed = client.post(
        f"/api/v1/allotments/{oid}/features",
        json={
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [0, 0]},
            "properties": {"kind": "bed"},
        },
        headers=other,
    ).json["id"]
    theirs = client.post(
        f"/api/v1/allotments/{oid}/plan-items",
        json={
            "feature_id": bed,
            "crop_key": "lettuce",
            "area_m2": 1,
            "sow_on": "2027-03-01",
            "end_on": "2027-05-01",
        },
        headers=other,
    ).json["id"]
    resp = sow(client, plot, INSIDE, plan_item_id=theirs)
    assert resp.status_code == 422 and "allotment" in resp.json["message"]


def test_an_item_can_only_be_planted_once(client, plot):  # noqa: F811
    item = planned(client, plot)
    assert sow(client, plot, INSIDE, plan_item_id=item["id"]).status_code == 201
    again = sow(client, plot, INSIDE, plan_item_id=item["id"])
    assert again.status_code == 409 and "already" in again.json["message"]
    skipped = planned(client, plot)
    client.patch(
        f"{plot['base']}/plan-items/{skipped['id']}",
        json={"status": "skipped"},
        headers=plot["editor"],
    )
    assert sow(client, plot, INSIDE, plan_item_id=skipped["id"]).status_code == 409


def test_a_transplant_goes_through_a_tray(client, plot):  # noqa: F811
    item = planned(
        client, plot, crop_key="tomato", method="transplant",
        plant_out_on=(TODAY + timedelta(days=30)).isoformat(),
    )  # fmt: skip
    resp = sow(client, plot, INSIDE, plan_item_id=item["id"])
    assert resp.status_code == 422 and "tray" in resp.json["message"]
    assert item_now(client, plot, item["id"])["status"] == "planned"


def test_a_refused_region_leaves_the_item_planned(client, plot):  # noqa: F811
    item = planned(client, plot)
    outside = {"type": "Polygon", "coordinates": [[[5, 5], [5.001, 5], [5.001, 5.001], [5, 5]]]}
    assert sow(client, plot, outside, plan_item_id=item["id"]).status_code == 422
    assert item_now(client, plot, item["id"])["status"] == "planned"


def test_planting_it_takes_its_unstarted_tasks_out_of_the_plan(client, plot):  # noqa: F811
    item = planned(client, plot)
    client.post(f"{plot['base']}/plan/tasks", json={}, headers=plot["editor"])
    sow(client, plot, INSIDE, plan_item_id=item["id"])
    out = client.get(f"{plot['base']}/plan/task-suggestions", headers=plot["viewer"]).json
    assert out["stale"] == 2 and out["suggestions"] == []  # it is planted: nothing left to suggest
    synced = client.post(f"{plot['base']}/plan/tasks/sync", json={}, headers=plot["editor"]).json
    assert synced == {"updated": 0, "removed": 2}


@pytest.mark.parametrize("who,code", [("viewer", 403), ("stranger", 404)])
def test_roles_still_apply(client, plot, who, code):  # noqa: F811
    item = planned(client, plot)
    assert sow(client, plot, INSIDE, who=who, plan_item_id=item["id"]).status_code == code
