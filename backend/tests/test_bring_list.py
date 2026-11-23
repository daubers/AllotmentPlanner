from allotment.bring_list import MAX_SUGGESTED_PER_TASK, TaskNeed, compute_bring


def brief(i, name, status="in_service"):
    return {
        "id": i,
        "name": name,
        "kind": None,
        "kind_label": "Other",
        "quantity": 1,
        "status": status,
    }


CATALOG = {
    1: brief(1, "Border spade"),
    2: brief(2, "Fork"),
    3: brief(3, "Dibber"),
    4: brief(4, "Cloche"),
    5: brief(5, "Wheelbarrow"),
}


def ids(rows):
    return [r["id"] for r in rows]


def need(task_id, own=(), suggested=(), done=False):
    return TaskNeed(task_id, done, tuple(own), tuple(suggested))


def test_the_tools_on_the_tasks_are_listed_once_with_who_needs_them():
    rows = compute_bring([need(10, own=[1, 2]), need(11, own=[2, 3])], {}, CATALOG)
    assert ids(rows) == [1, 3, 2]  # Border spade, Dibber, Fork: by name
    assert {r["id"]: r["task_ids"] for r in rows} == {1: [10], 2: [10, 11], 3: [11]}
    assert all(r["source"] == "task" for r in rows)


def test_sorted_by_why_then_name():
    rows = compute_bring(
        [need(10, own=[2]), need(11, suggested=[3])], {5: "add", 4: "add"}, CATALOG
    )
    assert [(r["id"], r["source"]) for r in rows] == [
        (2, "task"),
        (3, "suggested"),
        (4, "extra"),
        (5, "extra"),
    ]
    assert ids(compute_bring([need(10, own=[5, 1, 3])], {}, CATALOG)) == [1, 3, 5]  # by name


def test_a_task_without_tools_borrows_its_suggestions_but_only_a_couple():
    rows = compute_bring([need(10, suggested=[1, 2, 3, 4])], {}, CATALOG)
    assert ids(rows) == [1, 2] and len(rows) == MAX_SUGGESTED_PER_TASK
    assert all(r["source"] == "suggested" for r in rows)


def test_a_task_with_tools_does_not_borrow():
    rows = compute_bring([need(10, own=[3], suggested=[1, 2])], {}, CATALOG)
    assert ids(rows) == [3]


def test_a_finished_task_needs_nothing():
    assert (
        compute_bring(
            [need(10, own=[1], done=True), need(11, suggested=[2], done=True)], {}, CATALOG
        )
        == []
    )


def test_a_tool_that_is_needed_and_suggested_counts_as_needed():
    rows = compute_bring([need(10, suggested=[1]), need(11, own=[1])], {}, CATALOG)
    assert [(r["id"], r["source"], r["task_ids"]) for r in rows] == [(1, "task", [10, 11])]


def test_extras_add_and_remove():
    rows = compute_bring(
        [need(10, own=[1, 2]), need(11, suggested=[3])],
        {2: "remove", 3: "remove", 4: "add"},
        CATALOG,
    )
    assert [(r["id"], r["source"]) for r in rows] == [(1, "task"), (4, "extra")]


def test_adding_what_a_task_already_needs_changes_nothing():
    rows = compute_bring([need(10, own=[1])], {1: "add"}, CATALOG)
    assert [(r["id"], r["source"], r["task_ids"]) for r in rows] == [(1, "task", [10])]


def test_an_item_that_no_longer_exists_is_dropped():
    rows = compute_bring([need(10, own=[1, 99])], {98: "add"}, CATALOG)
    assert ids(rows) == [1]


def test_equipment_out_of_action_stays_on_the_list_but_says_so():
    catalog = {1: brief(1, "Spade", "out_of_action")}
    (row,) = compute_bring([need(10, own=[1])], {}, catalog)
    assert row["status"] == "out_of_action"


def test_nothing_in_nothing_out():
    assert compute_bring([], {}, CATALOG) == []
    assert compute_bring([need(10)], {}, CATALOG) == []
