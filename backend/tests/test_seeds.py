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


# --- trays -------------------------------------------------------------------------------------

from datetime import date  # noqa: E402
from types import SimpleNamespace as Cell  # noqa: E402

import pytest  # noqa: E402

from allotment.seeds import (  # noqa: E402
    CellChangeError,
    apply_cell_change,
    cells_outside,
    tray_counts,
    tray_kinds,
)

TODAY = date(2026, 3, 10)
TRAY_DAY = date(2026, 3, 1)


def sown(**kw):
    return {
        "packet_id": 1,
        "count": 2,
        "status": "sown",
        "sown_on": TRAY_DAY,
        "germinated_on": None,
        "note": "",
        **kw,
    }


def test_sowing_an_empty_cell_uses_the_tray_date_and_one_seed():
    new = apply_cell_change(None, {"packet_id": 4}, TRAY_DAY, TODAY)
    assert (new["status"], new["packet_id"], new["count"], new["sown_on"]) == (
        "sown",
        4,
        1,
        TRAY_DAY,
    )


def test_sowing_without_a_tray_date_uses_today_and_a_given_count():
    new = apply_cell_change(None, {"packet_id": 4, "count": 3}, None, TODAY)
    assert (new["count"], new["sown_on"]) == (3, TODAY)


def test_germinating_stamps_the_date_and_keeps_the_rest():
    new = apply_cell_change(sown(), {"status": "germinated"}, TRAY_DAY, TODAY)
    assert (new["status"], new["germinated_on"], new["packet_id"], new["count"]) == (
        "germinated",
        TODAY,
        1,
        2,
    )
    given = apply_cell_change(
        sown(), {"status": "germinated", "germinated_on": TRAY_DAY}, None, TODAY
    )
    assert given["germinated_on"] == TRAY_DAY


def test_going_back_to_sown_clears_germination():
    germ = sown(status="germinated", germinated_on=TODAY)
    assert apply_cell_change(germ, {"status": "sown"}, None, TODAY)["germinated_on"] is None


def test_resowing_a_cell_with_a_new_packet_keeps_its_state():
    new = apply_cell_change(sown(), {"packet_id": 9}, None, TODAY)
    assert (new["packet_id"], new["status"]) == (9, "sown")


def test_empty_clears_the_cell():
    assert apply_cell_change(sown(), {"status": "empty"}, None, TODAY) is None
    assert apply_cell_change(None, {"status": "empty"}, None, TODAY) is None


@pytest.mark.parametrize("change", [{"status": "germinated"}, {"status": "failed"}, {"note": "x"}])
def test_nothing_to_germinate_or_fail_in_an_empty_cell(change):
    with pytest.raises(CellChangeError):
        apply_cell_change(None, change, None, TODAY)


def test_a_planted_out_cell_is_left_alone():
    with pytest.raises(CellChangeError):
        apply_cell_change(sown(status="planted_out"), {"status": "failed"}, None, TODAY)


def test_counts_and_kinds():
    cells = [
        Cell(status="sown", packet_id=1, count=2, row=0, col=0),
        Cell(status="germinated", packet_id=1, count=1, row=0, col=1),
        Cell(status="failed", packet_id=2, count=None, row=1, col=0),
        Cell(status="sown", packet_id=None, count=1, row=1, col=1),
    ]
    assert tray_counts(2, 3, cells) == {
        "empty": 2,
        "sown": 2,
        "germinated": 1,
        "failed": 1,
        "planted_out": 0,
    }
    assert tray_kinds(cells) == [
        {"packet_id": 1, "cells": 2, "seeds": 3},
        {"packet_id": 2, "cells": 1, "seeds": 0},
    ]
    assert [(c.row, c.col) for c in cells_outside(cells, 1, 2)] == [(1, 0), (1, 1)]
