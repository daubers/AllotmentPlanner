"""Suggested tasks from sow dates: what to do next with a tray or a planting. Pure, no database.

The dates come from the seed packet: days to germinate and to mature, and the calendar's plant-out
and harvest months. Where a packet gives nothing, a default is used or the step is left out.
A step whose date has passed is not suggested, so a tray sown weeks ago does not get a stale list.
"""

from dataclasses import dataclass
from datetime import date, timedelta

DEFAULT_GERMINATION_DAYS = 7
PRICK_OUT_AFTER_DAYS = 14  # after germination
THIN_AFTER_DAYS = 14  # after germination
READY_TO_PLANT_OUT_DAYS = 28  # after germination: a seedling worth moving
HARDEN_OFF_DAYS = 7  # before planting out


@dataclass(frozen=True)
class Suggestion:
    key: str
    title: str
    description: str
    due_date: date


@dataclass(frozen=True)
class Sowing:
    """One kind of seed sown on one day, with what the packet says about it."""

    packet_id: int
    name: str
    sown_on: date
    germinated: bool = False
    germinate_days_min: int | None = None
    maturity_days_min: int | None = None
    plant_out_months: tuple[int, ...] = ()
    harvest_months: tuple[int, ...] = ()


def _first_in_months(start: date, months: tuple[int, ...]) -> date | None:
    """``start`` if its month is in ``months``, else the first day of the next month that is."""
    if not months:
        return None
    for ahead in range(0, 13):
        month_index = start.month - 1 + ahead
        year, month = start.year + month_index // 12, month_index % 12 + 1
        if month in months:
            return start if ahead == 0 else date(year, month, 1)
    return None


def germination_date(s: Sowing) -> date:
    return s.sown_on + timedelta(days=s.germinate_days_min or DEFAULT_GERMINATION_DAYS)


def plant_out_date(s: Sowing) -> date:
    """When seedlings are big enough and the packet's calendar allows planting out."""
    ready = germination_date(s) + timedelta(days=READY_TO_PLANT_OUT_DAYS)
    return _first_in_months(ready, s.plant_out_months) or ready


def harvest_date(s: Sowing, after: date) -> date | None:
    if s.maturity_days_min:
        return s.sown_on + timedelta(days=s.maturity_days_min)
    return _first_in_months(after, s.harvest_months)


def suggest_for_tray(
    tray_id: int, tray_name: str, sowings: list[Sowing], today: date
) -> list[Suggestion]:
    """Germination check, prick out, harden off, plant out and harvest, per kind in the tray."""
    out: list[Suggestion] = []
    for s in sowings:
        base = f"tray:{tray_id}:{s.packet_id}"
        where = f"{s.name} in {tray_name}, sown {s.sown_on:%-d %b}"
        germ = germination_date(s)
        plant_out = plant_out_date(s)
        steps = [
            ("germination", f"Check germination: {s.name}", germ, not s.germinated),
            (
                "prick-out",
                f"Prick out {s.name} if crowded",
                germ + timedelta(days=PRICK_OUT_AFTER_DAYS),
                True,
            ),
            (
                "harden-off",
                f"Harden off {s.name}",
                plant_out - timedelta(days=HARDEN_OFF_DAYS),
                True,
            ),
            ("plant-out", f"Plant out {s.name}", plant_out, True),
        ]
        harvest = harvest_date(s, plant_out)
        if harvest:
            steps.append(("harvest", f"Harvest {s.name}", harvest, True))
        out += [
            Suggestion(f"{base}:{step}", title, where, due)
            for step, title, due, wanted in steps
            if wanted and due >= today
        ]
    return sorted(out, key=lambda x: (x.due_date, x.key))


def suggest_for_planting(
    planting_id: int, label: str, s: Sowing, method: str, status: str, harvested: bool, today: date
) -> list[Suggestion]:
    """Germination check and thinning for a direct sowing, then harvest. Nothing once it is over."""
    if status in ("finished", "failed"):
        return []
    base = f"planting:{planting_id}"
    where = f"{label}, sown {s.sown_on:%-d %b}"
    germ = germination_date(s)
    steps: list[tuple[str, str, date]] = []
    if method == "direct_sow" and status == "sown":
        steps += [
            ("germination", f"Check germination: {s.name}", germ),
            ("thin", f"Thin {s.name}", germ + timedelta(days=THIN_AFTER_DAYS)),
        ]
    harvest = None if harvested else harvest_date(s, germ)
    if harvest:
        steps.append(("harvest", f"Harvest {s.name}", harvest))
    return sorted(
        (
            Suggestion(f"{base}:{step}", title, where, due)
            for step, title, due in steps
            if due >= today
        ),
        key=lambda x: (x.due_date, x.key),
    )
