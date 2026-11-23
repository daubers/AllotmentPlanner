"""Equipment on tasks: loading it, setting it, and suggesting it. Needs the database.

The matching itself is pure and lives in allotment.equipment_kinds.
"""

from flask_smorest import abort

from .equipment_kinds import Item, kind_label, match_items, parse_keywords, suggest_kinds
from .extensions import db
from .models import Equipment, MapFeature, Task, TaskEquipment


def equipment_brief(item: Equipment) -> dict:
    """What a task or a suggestion shows of an item."""
    return {
        "id": item.id,
        "name": item.name,
        "kind": item.kind,
        "kind_label": kind_label(item.kind),
        "quantity": item.quantity,
        "status": item.status,
    }


def equipment_for_tasks(task_ids: list[int]) -> dict[int, list[dict]]:
    """The equipment on each task, in one query. Tasks with none are left out."""
    if not task_ids:
        return {}
    rows = (
        db.session.query(TaskEquipment.task_id, Equipment)
        .join(Equipment, Equipment.id == TaskEquipment.equipment_id)
        .filter(TaskEquipment.task_id.in_(task_ids))
        .order_by(db.func.lower(Equipment.name), Equipment.id)
    )
    out: dict[int, list[dict]] = {}
    for task_id, item in rows:
        out.setdefault(task_id, []).append(equipment_brief(item))
    return out


def set_task_equipment(
    task: Task, equipment_ids: list[int], allotment, user_id: int | None
) -> None:
    """Make ``equipment_ids`` exactly the equipment on ``task`` (added, not committed).

    Every id must be an item of this allotment, otherwise nothing is changed and the request is
    refused.
    """
    wanted = list(dict.fromkeys(equipment_ids))
    if wanted:
        found = {
            i
            for (i,) in db.session.query(Equipment.id).filter(
                Equipment.id.in_(wanted), Equipment.allotment_id == allotment.id
            )
        }
        if found != set(wanted):
            db.session.rollback()
            abort(422, message="equipment_ids must all belong to this allotment")
    have = {
        row.equipment_id: row for row in db.session.query(TaskEquipment).filter_by(task_id=task.id)
    }
    changed = {i for i in have if i not in wanted} | {i for i in wanted if i not in have}
    for equipment_id, row in have.items():
        if equipment_id not in wanted:
            db.session.delete(row)
    for equipment_id in wanted:
        if equipment_id not in have:
            db.session.add(
                TaskEquipment(
                    allotment_id=allotment.id,
                    task_id=task.id,
                    equipment_id=equipment_id,
                    created_by=user_id,
                )
            )
    if changed:
        from .visit_bring import touch_visits_for_tasks  # here: visit_bring imports this module

        touch_visits_for_tasks([task.id])


def load_equipment(allotment_id: int) -> tuple[list[Item], dict[int, Equipment]]:
    """The allotment's equipment, as matching input and as rows, from one query."""
    rows = (
        db.session.query(Equipment)
        .filter_by(allotment_id=allotment_id)
        .order_by(Equipment.id)
        .all()
    )
    items = [Item(e.id, e.name, e.kind, e.status, tuple(parse_keywords(e.used_for))) for e in rows]
    return items, {e.id: e for e in rows}


def suggest_equipment(
    items: list[Item],
    by_id: dict[int, Equipment],
    *,
    title: str = "",
    description: str = "",
    key: str | None = None,
    feature_kind: str | None = None,
    exclude: set[int] | frozenset[int] = frozenset(),
) -> list[dict]:
    """The items to suggest for a job, each as its brief plus the ``reason``."""
    hits = suggest_kinds(title, description, key, feature_kind)
    return [
        {**equipment_brief(by_id[m.item_id]), "reason": m.reason}
        for m in match_items(hits, items, title, description, exclude)
        if m.item_id in by_id
    ]


def feature_kinds(feature_ids: set[int]) -> dict[int, str]:
    """The kind (bed, shed...) of each map feature, in one query."""
    if not feature_ids:
        return {}
    rows = db.session.query(MapFeature.id, MapFeature.kind).filter(MapFeature.id.in_(feature_ids))
    return dict(rows.all())


def add_equipment_suggestions(allotment_id: int, rows: list[dict]) -> list[dict]:
    """Give each suggested task (a dict with key, title, description) an ``equipment`` list.

    Only equipment you own is ever suggested, so an allotment with none gets empty lists.
    """
    items, by_id = load_equipment(allotment_id)
    for row in rows:
        row["equipment"] = (
            suggest_equipment(
                items,
                by_id,
                title=row.get("title", ""),
                description=row.get("description", ""),
                key=row.get("key"),
            )
            if items
            else []
        )
    return rows
