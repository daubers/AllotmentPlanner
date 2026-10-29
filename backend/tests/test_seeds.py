from allotment.seeds import is_due, normalise_calendar, range_problem


def test_normalise_fills_every_activity_and_tidies_months():
    cal = normalise_calendar({"sow_indoors": [3, 2, 3, 13, 0], "bogus": [1]})
    assert cal == {"sow_indoors": [2, 3], "sow_outdoors": [], "plant_out": [], "harvest": []}


def test_normalise_copes_with_nothing():
    assert normalise_calendar(None)["harvest"] == []


def test_sow_means_indoors_or_outdoors():
    cal = {"sow_indoors": [2], "sow_outdoors": [5], "harvest": [9]}
    assert is_due(cal, 2) and is_due(cal, 5)
    assert not is_due(cal, 9)
    assert is_due(cal, 9, "harvest")
    assert not is_due(cal, 2, "sow_outdoors")


def test_a_range_the_wrong_way_round_is_reported():
    assert range_problem(10, 5, "Days to germinate")
    assert range_problem(5, 10, "x") is None
    assert range_problem(None, 10, "x") is None
