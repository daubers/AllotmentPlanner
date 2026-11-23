"""Crop plans: when a bed is occupied and whether it is overbooked. Pure, no database."""

from datetime import date, timedelta

PLAN_STATUSES = ("planned", "done", "skipped")
MAX_SUCCESSION = 30
EPSILON_M2 = 0.01  # areas are rounded by people; don't flag a hundredth of a square metre


def occupied_from(item) -> date:
    """The day a bed starts being used: planting out for a transplant, sowing for a direct sow."""
    return item.plant_out_on or item.sow_on


def date_problem(method: str, sow_on: date, plant_out_on: date | None, end_on: date) -> str | None:
    """A message if the dates can't describe a crop in a bed; None if they can."""
    if method == "transplant" and plant_out_on is None:
        return "A transplant needs a plant-out date"
    if method == "direct_sow" and plant_out_on is not None:
        return "A direct sow has no plant-out date"
    if plant_out_on is not None and plant_out_on < sow_on:
        return "The plant-out date is before the sowing date"
    if end_on < (plant_out_on or sow_on):
        return "The bed-free date is before the crop goes in"
    return None


def overlaps_window(item, start: date, end: date) -> bool:
    """Whether the item has anything to do with the window [start, end] (tray time included)."""
    return item.sow_on <= end and item.end_on >= start


def conflicts(items, capacity_m2: float | None) -> list[dict]:
    """The stretches of time when the planned items need more space than the bed has.

    Occupancy is half open, [occupied_from, end_on), so one crop ending the day the next starts is
    not a clash. Items that are skipped are ignored. Returns [] when the bed's size is unknown.
    Each result is {start, to, used_m2, over_m2, item_ids}, with ``to`` the first free day.
    """
    if capacity_m2 is None:
        return []
    live = [i for i in items if i.status != "skipped" and occupied_from(i) < i.end_on]
    days = sorted({occupied_from(i) for i in live} | {i.end_on for i in live})
    found: list[dict] = []
    for start, stop in zip(days, days[1:], strict=False):
        active = [i for i in live if occupied_from(i) <= start and i.end_on >= stop]
        used = sum(i.area_m2 for i in active)
        if used <= capacity_m2 + EPSILON_M2:
            continue
        ids = sorted(i.id for i in active)
        last = found[-1] if found else None
        if last and last["to"] == start and last["item_ids"] == ids:
            last["to"] = stop
            continue
        found.append(
            {
                "start": start,
                "to": stop,
                "used_m2": round(used, 2),
                "over_m2": round(used - capacity_m2, 2),
                "item_ids": ids,
            }
        )
    return found


def shifted(d: date | None, days: int) -> date | None:
    return None if d is None else d + timedelta(days=days)
