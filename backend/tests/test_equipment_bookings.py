from datetime import date
from types import SimpleNamespace

from allotment.equipment_bookings import booking_conflicts, date_problem, overlapping

D = date


def booking(i, quantity, start, end):
    return SimpleNamespace(id=i, quantity=quantity, starts_on=start, ends_on=end)


def test_dates():
    assert date_problem(D(2026, 3, 1), D(2026, 4, 1)) is None
    assert "free after" in date_problem(D(2026, 3, 1), D(2026, 3, 1))
    assert date_problem(D(2026, 3, 2), D(2026, 3, 1))


def test_no_clash_when_you_own_enough():
    a = booking(1, 3, D(2026, 3, 1), D(2026, 5, 1))
    b = booking(2, 3, D(2026, 4, 1), D(2026, 6, 1))
    assert booking_conflicts([a, b], 6) == []
    assert booking_conflicts([], 6) == []


def test_six_cloches_cannot_cover_eight():
    a = booking(1, 5, D(2026, 3, 1), D(2026, 5, 1))
    b = booking(2, 3, D(2026, 4, 1), D(2026, 6, 1))
    assert booking_conflicts([a, b], 6) == [
        {"start": D(2026, 4, 1), "to": D(2026, 5, 1), "used": 8, "over": 2, "booking_ids": [1, 2]}
    ]


def test_back_to_back_is_not_a_clash():
    a = booking(1, 6, D(2026, 3, 1), D(2026, 4, 1))
    b = booking(2, 6, D(2026, 4, 1), D(2026, 5, 1))  # starts the day a is free
    assert booking_conflicts([a, b], 6) == []


def test_stretches_with_the_same_bookings_are_joined_and_others_are_separate():
    a = booking(1, 4, D(2026, 3, 1), D(2026, 9, 1))
    b = booking(2, 4, D(2026, 4, 1), D(2026, 6, 1))
    c = booking(3, 1, D(2026, 5, 1), D(2026, 5, 15))
    got = booking_conflicts([a, b, c], 6)
    assert [(g["start"], g["to"], g["booking_ids"], g["used"]) for g in got] == [
        (D(2026, 4, 1), D(2026, 5, 1), [1, 2], 8),
        (D(2026, 5, 1), D(2026, 5, 15), [1, 2, 3], 9),
        (D(2026, 5, 15), D(2026, 6, 1), [1, 2], 8),
    ]


def test_a_booking_that_covers_it_all_reports_one_run():
    a = booking(1, 7, D(2026, 3, 1), D(2026, 4, 1))
    b = booking(2, 7, D(2026, 3, 1), D(2026, 4, 1))
    assert len(booking_conflicts([a, b], 6)) == 1


def test_only_the_conflicts_a_booking_is_part_of():
    a = booking(1, 5, D(2026, 3, 1), D(2026, 4, 1))
    b = booking(2, 3, D(2026, 3, 15), D(2026, 4, 1))
    c = booking(3, 6, D(2026, 8, 1), D(2026, 9, 1))
    d = booking(4, 1, D(2026, 8, 1), D(2026, 9, 1))
    conflicts = booking_conflicts([a, b, c, d], 6)
    assert [x["booking_ids"] for x in conflicts] == [[1, 2], [3, 4]]
    assert overlapping(conflicts, a) == [conflicts[0]]
    assert overlapping(conflicts, d) == [conflicts[1]]
    assert overlapping(conflicts, booking(9, 1, D(2026, 1, 1), D(2026, 1, 2))) == []
