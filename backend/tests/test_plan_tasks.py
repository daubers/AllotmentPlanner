from datetime import date
from types import SimpleNamespace

from allotment.plan_tasks import plan_tasks

D = date
BEDS = {5: "Bed 1", 6: "Bed 2"}


def item(i, name, sow, end, out=None, bed=5, series=None, status="planned", area=2.0, count=None):
    return SimpleNamespace(
        id=i,
        name=name,
        sow_on=sow,
        end_on=end,
        plant_out_on=out,
        feature_id=bed,
        series_key=series,
        status=status,
        area_m2=area,
        plant_count=count,
        method="transplant" if out else "direct_sow",
    )


def keys(tasks):
    return [t.key for t in tasks]


def test_a_direct_sow_is_sown_then_cleared():
    tasks = plan_tasks([item(1, "Lettuce", D(2026, 3, 1), D(2026, 5, 10), count=12)], BEDS)
    assert keys(tasks) == ["plan:sow:1", "plan:change:1:end"]
    sow, clear = tasks
    assert (sow.title, sow.due_date, sow.feature_id, sow.plan_item_id) == (
        "Sow Lettuce in Bed 1",
        D(2026, 3, 1),
        5,
        1,
    )
    assert "2 m², 12 plants" in sow.description
    assert (clear.title, clear.due_date) == ("Clear Lettuce in Bed 1", D(2026, 5, 10))


def test_a_transplant_is_sown_in_trays_planted_out_and_cleared():
    tasks = plan_tasks(
        [item(1, "Tomato", D(2026, 2, 20), D(2026, 10, 5), out=D(2026, 5, 20))], BEDS
    )
    assert keys(tasks) == ["plan:sow:1", "plan:plant:1", "plan:change:1:end"]
    assert tasks[0].title == "Sow Tomato in Bed 1 (in trays)"
    assert (tasks[1].title, tasks[1].due_date) == ("Plant out Tomato in Bed 1", D(2026, 5, 20))


def test_the_next_crop_in_the_bed_is_named():
    a = item(1, "Garlic", D(2026, 11, 1), D(2027, 7, 20))
    b = item(2, "Carrot", D(2027, 8, 1), D(2027, 11, 30))
    tasks = plan_tasks([a, b], BEDS)
    clear = next(t for t in tasks if t.key.startswith("plan:change:1"))
    assert clear.key == "plan:change:1:2"
    assert clear.title == "Clear Garlic in Bed 1 and prepare for Carrot"
    assert clear.due_date == D(2027, 7, 20)
    assert "plan:change:2:end" in keys(tasks)


def test_a_crop_starting_the_day_the_bed_is_free_follows():
    a = item(1, "Pea", D(2026, 3, 1), D(2026, 6, 1))
    b = item(2, "Leek", D(2026, 6, 1), D(2026, 12, 1))
    assert "plan:change:1:2" in keys(plan_tasks([a, b], BEDS))


def test_crops_that_overlap_are_not_changed_over():
    tall = item(1, "Beans", D(2026, 5, 1), D(2026, 9, 1))
    under = item(2, "Lettuce", D(2026, 6, 1), D(2026, 8, 1))  # grows underneath, ends first
    tasks = plan_tasks([tall, under], BEDS)
    assert "plan:change:1:end" in keys(tasks) and "plan:change:2:end" in keys(tasks)
    assert not any(":change:" in k and not k.endswith(":end") for k in keys(tasks))


def test_a_succession_is_not_changed_over_into_itself():
    a = item(1, "Lettuce", D(2026, 3, 1), D(2026, 4, 1), series="s")
    b = item(2, "Lettuce", D(2026, 4, 1), D(2026, 5, 1), series="s")  # touches a, same run
    c = item(3, "Radish", D(2026, 5, 1), D(2026, 6, 1))
    changes = [k for k in keys(plan_tasks([a, b, c], BEDS)) if ":change:" in k]
    assert changes == ["plan:change:1:3", "plan:change:2:3", "plan:change:3:end"]


def test_beds_are_kept_apart():
    a = item(1, "Pea", D(2026, 3, 1), D(2026, 6, 1), bed=5)
    b = item(2, "Leek", D(2026, 7, 1), D(2026, 12, 1), bed=6)
    tasks = plan_tasks([a, b], BEDS)
    assert "plan:change:1:end" in keys(tasks)  # Leek is in another bed
    assert next(t for t in tasks if t.key == "plan:sow:2").title == "Sow Leek in Bed 2"


def test_only_planned_items_make_tasks():
    done = item(1, "Pea", D(2026, 3, 1), D(2026, 6, 1), status="done")
    skipped = item(2, "Leek", D(2026, 3, 1), D(2026, 6, 1), status="skipped")
    after = item(3, "Kale", D(2026, 7, 1), D(2026, 12, 1))
    assert keys(plan_tasks([done, skipped, after], BEDS)) == ["plan:sow:3", "plan:change:3:end"]
    assert plan_tasks([], BEDS) == []


def test_keys_do_not_depend_on_dates():
    before = plan_tasks([item(1, "Lettuce", D(2026, 3, 1), D(2026, 5, 10))], BEDS)
    after = plan_tasks([item(1, "Lettuce", D(2026, 4, 9), D(2026, 6, 30))], BEDS)
    assert keys(before) == keys(after)
    assert [t.due_date for t in before] != [t.due_date for t in after]


def test_sorted_by_due_date_and_a_missing_bed_name_is_tolerated():
    tasks = plan_tasks([item(1, "Pea", D(2026, 3, 1), D(2026, 6, 1), bed=99)], BEDS)
    assert [t.due_date for t in tasks] == sorted(t.due_date for t in tasks)
    assert tasks[0].title == "Sow Pea in the bed"
