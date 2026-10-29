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
