"""The tasks a crop plan implies: sow, plant out, and clear the bed at the end. Pure, no database.

Each task has a key built from plan item ids (never dates), so a task can be told apart from a
changed one and updated in place when the plan is edited:

    plan:sow:<item>            sow the crop (in the bed, or in a tray for a transplant)
    plan:plant:<item>          plant a transplant out
    plan:change:<item>:<next>  clear the crop when its time is up, and prepare for the next one
    plan:change:<item>:end     clear the crop; nothing is planned after it

Only items that are still planned count. A crop is followed by the first item in the same bed that
starts on or after the day it ends and is not part of the same succession, so crops that overlap
(growing together) are not "changed over".
"""

from dataclasses import dataclass
from datetime import date

from .plan import occupied_from

PREFIX = "plan:"


@dataclass(frozen=True)
class PlanTask:
    key: str
    title: str
    description: str
    due_date: date
    feature_id: int
    plan_item_id: int


def _nice(d: date) -> str:
    return f"{d.day} {d.strftime('%b')}"


def _about(item) -> str:
    bits = [f"{item.area_m2:g} m²"]
    if item.plant_count:
        bits.append(f"{item.plant_count} plants")
    return ", ".join(bits)


def _next_crop(item, items):
    """The first item starting once this one ends (not another sowing in the same succession)."""
    later = [
        o
        for o in items
        if o.id != item.id
        and occupied_from(o) >= item.end_on
        and not (item.series_key and o.series_key == item.series_key)
    ]
    return min(later, key=lambda o: (occupied_from(o), o.id), default=None)


def plan_tasks(items, bed_names: dict[int, str]) -> list[PlanTask]:
    """Every task the planned items imply, past dates included, sorted by due date."""
    live = [i for i in items if i.status == "planned"]
    out: list[PlanTask] = []
    for item in live:
        bed = bed_names.get(item.feature_id) or "the bed"
        where = f"{item.name} in {bed}"
        tray = item.method == "transplant"
        out.append(
            PlanTask(
                f"{PREFIX}sow:{item.id}",
                f"Sow {where}" + (" (in trays)" if tray else ""),
                f"{_about(item)}. Planned for {_nice(item.sow_on)}.",
                item.sow_on,
                item.feature_id,
                item.id,
            )
        )
        if tray and item.plant_out_on:
            out.append(
                PlanTask(
                    f"{PREFIX}plant:{item.id}",
                    f"Plant out {where}",
                    f"{_about(item)}, from the trays sown on {_nice(item.sow_on)}.",
                    item.plant_out_on,
                    item.feature_id,
                    item.id,
                )
            )
        same_bed = [o for o in live if o.feature_id == item.feature_id]
        nxt = _next_crop(item, same_bed)
        if nxt is None:
            key, title = f"{PREFIX}change:{item.id}:end", f"Clear {where}"
            note = f"{item.name} is finished on {_nice(item.end_on)}; nothing is planned after it."
        else:
            key = f"{PREFIX}change:{item.id}:{nxt.id}"
            title = f"Clear {where} and prepare for {nxt.name}"
            note = f"{item.name} is finished on {_nice(item.end_on)}; {nxt.name} follows."
        out.append(PlanTask(key, title, note, item.end_on, item.feature_id, item.id))
    return sorted(out, key=lambda t: (t.due_date, t.key))
