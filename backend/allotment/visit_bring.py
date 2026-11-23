"""The bring list of visits, loaded for the API. Needs the database; the logic is in bring_list."""

from datetime import UTC, datetime

from flask_smorest import abort

from .bring_list import TaskNeed, compute_bring
from .extensions import db
from .models import Equipment, Task, TaskEquipment, TaskStatus, Visit, VisitEquipment, VisitTask
from .task_equipment import equipment_brief, equipment_for_tasks, load_equipment, suggest_equipment


def visit_brings(allotment_id: int, visits: list[Visit]) -> dict[int, dict]:
    """For each visit, its ``bring`` list and ``equipment_extras``, in a fixed number of queries."""
    if not visits:
        return {}
    task_ids = sorted({link.task_id for v in visits for link in v.tasks})
    rows = (
        db.session.query(
            Task.id, Task.status, Task.title, Task.description, Task.suggestion_key
        ).filter(Task.id.in_(task_ids))
        if task_ids
        else []
    )
    tasks = {r.id: r for r in rows}
    own = equipment_for_tasks(task_ids)
    items, by_id = load_equipment(allotment_id)
    catalog = {i: equipment_brief(e) for i, e in by_id.items()}
    extras: dict[int, dict[int, str]] = {v.id: {} for v in visits}
    for row in db.session.query(VisitEquipment).filter(
        VisitEquipment.visit_id.in_([v.id for v in visits])
    ):
        extras[row.visit_id][row.equipment_id] = row.mode

    suggested: dict[int, tuple[int, ...]] = {}

    def suggestions_for(task_id: int) -> tuple[int, ...]:
        if task_id not in suggested:
            t = tasks[task_id]
            hits = suggest_equipment(
                items,
                by_id,
                title=t.title,
                description=t.description,
                key=t.suggestion_key,
            )
            suggested[task_id] = tuple(h["id"] for h in hits)
        return suggested[task_id]

    out = {}
    for visit in visits:
        needs = []
        for link in visit.tasks:
            t = tasks.get(link.task_id)
            if t is None:
                continue
            mine = tuple(e["id"] for e in own.get(t.id, []))
            needs.append(
                TaskNeed(
                    t.id,
                    t.status == TaskStatus.DONE,
                    mine,
                    () if mine else suggestions_for(t.id),
                )
            )
        out[visit.id] = {
            "bring": compute_bring(needs, extras[visit.id], catalog),
            "equipment_extras": [
                {"equipment_id": i, "mode": m} for i, m in sorted(extras[visit.id].items())
            ],
        }
    return out


def bring_names(bring: list[dict]) -> list[str]:
    """The names for a calendar entry, in list order."""
    return [item["name"] for item in bring]


def set_visit_extras(
    visit: Visit, adds: list[int], removes: list[int], allotment, user_id: int | None
) -> None:
    """Make ``adds`` and ``removes`` the visit's hand-made changes (added, not committed).

    Every id must be this allotment's equipment and none may be in both lists; otherwise nothing
    changes and the request is refused.
    """
    wanted = {**dict.fromkeys(adds, "add"), **dict.fromkeys(removes, "remove")}
    if set(adds) & set(removes):
        abort(422, message="Equipment cannot be both added and removed")
    if wanted:
        found = {
            i
            for (i,) in db.session.query(Equipment.id).filter(
                Equipment.id.in_(wanted), Equipment.allotment_id == allotment.id
            )
        }
        if found != set(wanted):
            abort(422, message="equipment ids must all belong to this allotment")
    have = {
        r.equipment_id: r for r in db.session.query(VisitEquipment).filter_by(visit_id=visit.id)
    }
    for equipment_id, row in have.items():
        if wanted.get(equipment_id) != row.mode:
            db.session.delete(row)
    db.session.flush()
    for equipment_id, mode in wanted.items():
        if have.get(equipment_id) is None or have[equipment_id].mode != mode:
            db.session.add(
                VisitEquipment(
                    allotment_id=allotment.id,
                    visit_id=visit.id,
                    equipment_id=equipment_id,
                    mode=mode,
                    created_by=user_id,
                )
            )
    visit.updated_at = datetime.now(UTC)  # a changed list is a changed event for calendar apps


def _touch(visit_ids) -> None:
    ids = list(visit_ids)
    if ids:
        db.session.query(Visit).filter(Visit.id.in_(ids)).update(
            {"updated_at": datetime.now(UTC)}, synchronize_session=False
        )


def touch_visits_for_tasks(task_ids) -> None:
    """Mark the visits that have any of these tasks as changed (their bring list may differ)."""
    ids = list(task_ids)
    if ids:
        _touch(
            v for (v,) in db.session.query(VisitTask.visit_id).filter(VisitTask.task_id.in_(ids))
        )


def touch_visits_for_equipment(equipment_id: int) -> None:
    """Mark every visit that mentions this equipment (through a task or by hand) as changed."""
    via_tasks = (
        db.session.query(VisitTask.visit_id)
        .join(TaskEquipment, TaskEquipment.task_id == VisitTask.task_id)
        .filter(TaskEquipment.equipment_id == equipment_id)
    )
    by_hand = db.session.query(VisitEquipment.visit_id).filter(
        VisitEquipment.equipment_id == equipment_id
    )
    _touch({v for (v,) in via_tasks} | {v for (v,) in by_hand})
