from datetime import date
from types import SimpleNamespace

import pytest

from allotment.plan import conflicts, date_problem, occupied_from, overlaps_window, shifted


def item(i, area, sow, end, plant_out=None, status="planned"):
    return SimpleNamespace(
        id=i, area_m2=area, sow_on=sow, end_on=end, plant_out_on=plant_out, status=status
    )


D = date


def test_a_direct_sow_occupies_from_sowing_and_a_transplant_from_planting_out():
    assert occupied_from(item(1, 1, D(2026, 3, 1), D(2026, 6, 1))) == D(2026, 3, 1)
    assert occupied_from(item(1, 1, D(2026, 3, 1), D(2026, 6, 1), D(2026, 4, 20))) == D(2026, 4, 20)


def test_date_problems():
    ok = date_problem("direct_sow", D(2026, 3, 1), None, D(2026, 6, 1))
    assert ok is None
    assert "plant-out date" in date_problem("transplant", D(2026, 3, 1), None, D(2026, 6, 1))
    assert "no plant-out" in date_problem("direct_sow", D(2026, 3, 1), D(2026, 4, 1), D(2026, 6, 1))
    assert "before the sowing" in date_problem(
        "transplant", D(2026, 3, 1), D(2026, 2, 1), D(2026, 6, 1)
    )
    assert "before the crop" in date_problem("direct_sow", D(2026, 3, 1), None, D(2026, 2, 1))
    assert date_problem("transplant", D(2026, 3, 1), D(2026, 4, 1), D(2026, 4, 1)) is None


def test_overlaps_window_counts_tray_time():
    it = item(1, 1, D(2026, 3, 1), D(2026, 8, 1), D(2026, 5, 1))
    assert overlaps_window(it, D(2026, 3, 5), D(2026, 3, 20))  # still in the tray
    assert overlaps_window(it, D(2026, 8, 1), D(2026, 9, 1))  # the last day counts
    assert not overlaps_window(it, D(2026, 8, 2), D(2026, 9, 1))
    assert not overlaps_window(it, D(2026, 1, 1), D(2026, 2, 28))


def test_no_conflicts_when_the_bed_size_is_unknown():
    assert conflicts([item(1, 999, D(2026, 3, 1), D(2026, 6, 1))], None) == []


def test_fits_exactly_is_not_a_conflict():
    a = item(1, 6, D(2026, 3, 1), D(2026, 6, 1))
    b = item(2, 4, D(2026, 4, 1), D(2026, 7, 1))
    assert conflicts([a, b], 10) == []


def test_touching_successions_do_not_clash():
    a = item(1, 10, D(2026, 3, 1), D(2026, 4, 1))
    b = item(2, 10, D(2026, 4, 1), D(2026, 5, 1))  # starts the day a is free again
    assert conflicts([a, b], 10) == []


def test_overlap_is_reported_with_its_dates_and_amount():
    a = item(1, 6, D(2026, 3, 1), D(2026, 6, 1))
    b = item(2, 6, D(2026, 4, 1), D(2026, 5, 1))
    found = conflicts([a, b], 10)
    assert found == [
        {
            "start": D(2026, 4, 1),
            "to": D(2026, 5, 1),
            "used_m2": 12,
            "over_m2": 2,
            "item_ids": [1, 2],
        }
    ]


def test_three_way_overlap_and_adjacent_segments_merge():
    a = item(1, 5, D(2026, 3, 1), D(2026, 9, 1))
    b = item(2, 5, D(2026, 4, 1), D(2026, 9, 1))
    c = item(3, 5, D(2026, 5, 1), D(2026, 7, 1))
    found = conflicts([a, b, c], 12)
    # all three together exceed 12 only from May to July; a and b alone (10) fit
    assert [(f["start"], f["to"], f["used_m2"], f["item_ids"]) for f in found] == [
        (D(2026, 5, 1), D(2026, 7, 1), 15, [1, 2, 3])
    ]
    # over a smaller bed the two-item stretches before and after merge into one run per item set
    tight = conflicts([a, b, c], 8)
    assert [(f["start"], f["to"]) for f in tight] == [
        (D(2026, 4, 1), D(2026, 5, 1)),
        (D(2026, 5, 1), D(2026, 7, 1)),
        (D(2026, 7, 1), D(2026, 9, 1)),
    ]


def test_skipped_items_do_not_count():
    a = item(1, 8, D(2026, 3, 1), D(2026, 6, 1))
    b = item(2, 8, D(2026, 3, 1), D(2026, 6, 1), status="skipped")
    assert conflicts([a, b], 10) == []


def test_a_transplant_only_uses_the_bed_from_planting_out():
    tray = item(1, 9, D(2026, 2, 1), D(2026, 6, 1), D(2026, 5, 1))
    other = item(2, 9, D(2026, 3, 1), D(2026, 5, 1))
    assert conflicts([tray, other], 10) == []  # sown in a tray in Feb, in the bed from 1 May


def test_a_hundredth_of_a_square_metre_is_rounding_not_a_clash():
    a = item(1, 5.005, D(2026, 3, 1), D(2026, 6, 1))
    b = item(2, 5.0, D(2026, 3, 1), D(2026, 6, 1))
    assert conflicts([a, b], 10) == []


def test_shifted():
    assert shifted(D(2026, 3, 1), 14) == D(2026, 3, 15)
    assert shifted(None, 14) is None
    assert shifted(D(2026, 12, 25), 10) == D(2027, 1, 4)


@pytest.mark.parametrize("area", [0, -1])
def test_no_division_issues_with_odd_areas(area):
    assert conflicts([item(1, area, D(2026, 3, 1), D(2026, 4, 1))], 10) == []
