"""Seed packets: the sowing calendar and the checks around it. Pure, no database."""

ACTIVITIES = ("sow_indoors", "sow_outdoors", "plant_out", "harvest")
MONTHS = range(1, 13)
STOCK_LEVELS = ("full", "part", "low", "empty")
SUN_LEVELS = ("full", "partial", "shade")

# What "sow" means when asking "what can I sow this month?": either way of sowing counts.
SOW = ("sow_indoors", "sow_outdoors")


def normalise_calendar(calendar: dict | None) -> dict[str, list[int]]:
    """Every activity present, months unique and in order. Unknown keys are dropped."""
    calendar = calendar or {}
    return {
        a: sorted({int(m) for m in calendar.get(a, []) if int(m) in MONTHS}) for a in ACTIVITIES
    }


def is_due(calendar: dict | None, month: int, activity: str = "sow") -> bool:
    """Whether ``activity`` ("sow" = indoors or outdoors) falls in ``month`` (1 to 12)."""
    wanted = SOW if activity == "sow" else (activity,)
    cal = normalise_calendar(calendar)
    return any(month in cal[a] for a in wanted)


def range_problem(low: int | None, high: int | None, what: str) -> str | None:
    """A message if a min/max pair is the wrong way round; None if it is fine."""
    if low is not None and high is not None and low > high:
        return f"{what}: the minimum is more than the maximum"
    return None


# --- Trays -------------------------------------------------------------------------------------

CELL_STATUSES = ("sown", "germinated", "failed", "planted_out")  # "empty" = no row at all
MAX_TRAY_SIDE = 30
MAX_TRAY_CELLS = 400


def tray_counts(rows: int, cols: int, cells: list) -> dict[str, int]:
    """How many cells are in each state; every cell without a row is empty."""
    counts = {"empty": rows * cols, **dict.fromkeys(CELL_STATUSES, 0)}
    for c in cells:
        counts[c.status] += 1
        counts["empty"] -= 1
    return counts


def tray_kinds(cells: list) -> list[dict]:
    """The kinds of seed in a tray: cells and seeds sown per packet, most cells first."""
    kinds: dict[int, dict] = {}
    for c in cells:
        if c.packet_id is None:
            continue
        k = kinds.setdefault(c.packet_id, {"packet_id": c.packet_id, "cells": 0, "seeds": 0})
        k["cells"] += 1
        k["seeds"] += c.count or 0
    return sorted(kinds.values(), key=lambda k: (-k["cells"], k["packet_id"]))


def cells_outside(cells: list, rows: int, cols: int) -> list:
    """Cells that would fall off a tray resized to rows x cols."""
    return [c for c in cells if c.row >= rows or c.col >= cols]


class CellChangeError(ValueError):
    """A change that makes no sense for the cell as it stands."""


_BLANK_CELL = {
    "packet_id": None,
    "count": None,
    "status": None,
    "sown_on": None,
    "germinated_on": None,
    "note": "",
}


def apply_cell_change(current: dict | None, change: dict, default_sown_on, today) -> dict | None:
    """The cell after ``change``; None means it ends up empty.

    ``current`` is None for an empty cell. Only keys present in ``change`` are touched, except that
    the dates follow the status: germinating stamps ``germinated_on`` (today unless given) and
    going back to sown clears it. A new cell is sown on ``default_sown_on`` (the tray's date) or
    today, with one seed unless a count is given.
    """
    if current is not None and current["status"] == "planted_out":
        raise CellChangeError("already planted out")
    if change.get("status") == "empty":
        return None
    new = dict(current or _BLANK_CELL)
    for key in ("packet_id", "count", "sown_on", "germinated_on", "note"):
        if key in change:
            new[key] = change[key]
    status = change.get("status")
    if current is None:
        if status in ("germinated", "failed"):
            raise CellChangeError("nothing is sown there")
        if status is None and "packet_id" not in change:
            raise CellChangeError("nothing is sown there")
        status = "sown"
        new["sown_on"] = new["sown_on"] or default_sown_on or today
        new["count"] = new["count"] or 1
    if status is not None:
        new["status"] = status
        if status == "germinated":
            new["germinated_on"] = new["germinated_on"] or today
        elif status == "sown" and "germinated_on" not in change:
            new["germinated_on"] = None
    return new
