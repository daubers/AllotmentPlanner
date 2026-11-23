import uuid
from datetime import date, timedelta

from flask.views import MethodView
from flask_smorest import Blueprint, abort
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping

from .. import crops, events
from ..extensions import db
from ..models import FeatureKind, MapFeature, PlanItem, Role, SeedPacket, Task, TaskStatus
from ..plan import conflicts, date_problem, overlaps_window, shifted
from ..plan_tasks import PREFIX, PlanTask, plan_tasks
from ..plantings import bed_area_m2
from ..schemas import (
    PlanItemInSchema,
    PlanItemPatchSchema,
    PlanItemSchema,
    PlanQuerySchema,
    PlanSchema,
    PlanSuccessionSchema,
    PlanTasksAddSchema,
    PlanTasksQuerySchema,
    PlanTasksSchema,
    PlanTasksSyncResultSchema,
    TaskSchema,
)
from ..security import require_role
from ..task_equipment import add_equipment_suggestions, set_task_equipment
from .plantings import check_packet, get_bed
from .tasks import task_dicts

blp = Blueprint(
    "plan",
    __name__,
    url_prefix="/api/v1/allotments/<int:allotment_id>",
    description="Crop plan: what to grow in each bed, and when",
)

FIELDS = (
    "crop_key",
    "packet_id",
    "name",
    "method",
    "area_m2",
    "plant_count",
    "sow_on",
    "plant_out_on",
    "end_on",
    "notes",
    "status",
)


def item_to_dict(item: PlanItem) -> dict:
    return {
        "id": item.id,
        "feature_id": item.feature_id,
        "crop_key": item.crop_key,
        "packet_id": item.packet_id,
        "name": item.name,
        "method": item.method,
        "area_m2": item.area_m2,
        "plant_count": item.plant_count,
        "sow_on": item.sow_on,
        "plant_out_on": item.plant_out_on,
        "end_on": item.end_on,
        "series_key": item.series_key,
        "notes": item.notes,
        "status": item.status,
        "planting_id": item.planting_id,
        "created_at": item.created_at,
    }


def _get(allotment, item_id: int) -> PlanItem:
    item = db.session.get(PlanItem, item_id)
    if item is None or item.allotment_id != allotment.id:
        abort(404, message="Plan item not found")
    return item


def _check_bed(allotment, feature_id: int) -> MapFeature:
    bed = get_bed(allotment, feature_id)
    if bed.kind != FeatureKind.BED:
        abort(422, message="feature_id is not a bed")
    return bed


def _check_crop(crop_key: str | None) -> None:
    if crop_key and crops.get_crop(crop_key) is None:
        abort(422, message=f"Unknown crop: {crop_key}")


def _check_dates(method, sow_on, plant_out_on, end_on) -> None:
    problem = date_problem(method, sow_on, plant_out_on, end_on)
    if problem:
        abort(422, message=problem)


def _default_name(data: dict, allotment) -> str:
    """What to call an item that was not named: its packet, else its crop."""
    if data.get("name"):
        return data["name"]
    packet = db.session.get(SeedPacket, data["packet_id"]) if data.get("packet_id") else None
    if packet is not None and packet.allotment_id == allotment.id:
        return f"{packet.name} ({packet.variety})" if packet.variety else packet.name
    crop = crops.get_crop(data.get("crop_key"))
    if crop is not None:
        return crop.name
    abort(422, message="Give the item a name, a packet or a crop")


def _new_item(allotment, membership, data: dict, series_key: str | None = None) -> PlanItem:
    _check_bed(allotment, data["feature_id"])
    check_packet(allotment, data["packet_id"])
    _check_crop(data["crop_key"])
    _check_dates(data["method"], data["sow_on"], data["plant_out_on"], data["end_on"])
    return PlanItem(
        allotment_id=allotment.id,
        feature_id=data["feature_id"],
        crop_key=data["crop_key"],
        packet_id=data["packet_id"],
        name=_default_name(data, allotment),
        method=data["method"],
        area_m2=data["area_m2"],
        plant_count=data["plant_count"],
        sow_on=data["sow_on"],
        plant_out_on=data["plant_out_on"],
        end_on=data["end_on"],
        series_key=series_key,
        notes=data["notes"],
        created_by=membership.user_id,
    )


def _emit(kind: str, allotment, membership, item: PlanItem, **payload) -> None:
    events.emit(
        f"plan_item.{kind}",
        actor_id=membership.user_id,
        allotment_id=allotment.id,
        subject={"plan_item_id": item.id, "feature_id": item.feature_id},
        payload=payload,
    )


def _window(start: date | None, end: date | None) -> tuple[date, date]:
    """The default window is twelve months from the first of this month."""
    start = start or date.today().replace(day=1)
    if end is None:
        year, month = divmod(start.year * 12 + start.month - 1 + 12, 12)
        end = date(year, month + 1, 1) - timedelta(days=1)
    if end < start:
        abort(422, message="'to' is before 'from'")
    if (end - start).days > 800:
        abort(422, message="Ask for at most about two years at a time")
    return start, end


@blp.route("/plan")
class Plan(MethodView):
    @require_role(Role.VIEWER)
    @blp.arguments(PlanQuerySchema, location="query")
    @blp.response(200, PlanSchema)
    def get(self, args, allotment, membership):
        """Every bed with its plan items in the window, and when each is overbooked."""
        start, end = _window(args["start"], args["to"])
        beds = (
            db.session.query(MapFeature)
            .filter_by(allotment_id=allotment.id, kind=FeatureKind.BED)
            .order_by(MapFeature.name, MapFeature.id)
        )
        if args["feature_id"]:
            beds = beds.filter(MapFeature.id == args["feature_id"])
        out = []
        for bed in beds:
            items = (
                db.session.query(PlanItem)
                .filter_by(feature_id=bed.id)
                .order_by(PlanItem.sow_on, PlanItem.id)
                .all()
            )
            items = [i for i in items if overlaps_window(i, start, end)]
            area = bed_area_m2(mapping(to_shape(bed.geometry)))
            out.append(
                {
                    "feature_id": bed.id,
                    "name": bed.name,
                    "area_m2": area,
                    "items": [item_to_dict(i) for i in items],
                    "conflicts": conflicts(items, area),
                }
            )
        return {"start": start, "to": end, "beds": out}


@blp.route("/plan-items")
class PlanItems(MethodView):
    @require_role(Role.EDITOR)
    @blp.arguments(PlanItemInSchema)
    @blp.response(201, PlanItemSchema)
    def post(self, data, allotment, membership):
        """Plan a crop in a bed. Overbooking is shown on the plan, not refused."""
        item = _new_item(allotment, membership, data)
        db.session.add(item)
        db.session.commit()
        _emit("created", allotment, membership, item, crop=item.crop_key)
        return item_to_dict(item)


@blp.route("/plan-items/successions")
class PlanSuccessions(MethodView):
    @require_role(Role.EDITOR)
    @blp.arguments(PlanSuccessionSchema)
    @blp.response(201, PlanItemSchema(many=True))
    def post(self, data, allotment, membership):
        """Plan the same crop several times, each sowing a set number of days after the last."""
        template, gap = data["item"], data["interval_days"]
        series = str(uuid.uuid4())
        items = []
        for i in range(data["count"]):
            step = i * gap
            dated = {
                **template,
                "sow_on": shifted(template["sow_on"], step),
                "plant_out_on": shifted(template["plant_out_on"], step),
                "end_on": shifted(template["end_on"], step),
            }
            items.append(_new_item(allotment, membership, dated, series_key=series))
        db.session.add_all(items)  # nothing is saved if any step above was refused
        db.session.commit()
        for item in items:
            _emit("created", allotment, membership, item, crop=item.crop_key, series=series)
        return [item_to_dict(i) for i in items]


@blp.route("/plan-items/<int:item_id>")
class PlanItemDetail(MethodView):
    @require_role(Role.VIEWER)
    @blp.response(200, PlanItemSchema)
    def get(self, allotment, membership, item_id):
        return item_to_dict(_get(allotment, item_id))

    @require_role(Role.EDITOR)
    @blp.arguments(PlanItemPatchSchema)
    @blp.response(200, PlanItemSchema)
    def patch(self, data, allotment, membership, item_id):
        item = _get(allotment, item_id)
        if "packet_id" in data:
            check_packet(allotment, data["packet_id"])
        if "crop_key" in data:
            _check_crop(data["crop_key"])
        # Check the dates as they will be before changing anything: a refusal leaves no edit.
        final = {
            k: data.get(k, getattr(item, k)) for k in ("method", "sow_on", "plant_out_on", "end_on")
        }
        _check_dates(**final)
        for key in FIELDS:
            if key in data:
                setattr(item, key, data[key])
        db.session.commit()
        _emit("updated", allotment, membership, item, fields=sorted(data))
        return item_to_dict(item)

    @require_role(Role.EDITOR)
    @blp.response(204)
    def delete(self, allotment, membership, item_id):
        item = _get(allotment, item_id)
        # Its jobs that nobody has started go with it; started and finished ones stay (unlinked).
        db.session.query(Task).filter(
            Task.plan_item_id == item.id,
            Task.status == TaskStatus.TODO,
            Task.suggestion_key.like(f"{PREFIX}%"),
        ).delete(synchronize_session=False)
        db.session.delete(item)
        db.session.commit()
        _emit("deleted", allotment, membership, item)


# --- tasks that follow from the plan -------------------------------------------------------------


def _current(allotment, feature_id: int | None) -> list[PlanTask]:
    """Every task the plan implies right now, past dates included."""
    items = db.session.query(PlanItem).filter_by(allotment_id=allotment.id)
    if feature_id:
        items = items.filter(PlanItem.feature_id == feature_id)
    names = {
        f.id: f.name or f"Bed {f.id}"
        for f in db.session.query(MapFeature).filter_by(allotment_id=allotment.id)
    }
    return plan_tasks(items.all(), names)


def _existing(allotment, feature_id: int | None):
    rows = db.session.query(Task).filter(
        Task.allotment_id == allotment.id, Task.suggestion_key.like(f"{PREFIX}%")
    )
    return rows.filter(Task.feature_id == feature_id) if feature_id else rows


def _differs(task: Task, want: PlanTask) -> bool:
    return (task.title, task.description, task.due_date, task.feature_id, task.plan_item_id) != (
        want.title,
        want.description,
        want.due_date,
        want.feature_id,
        want.plan_item_id,
    )


@blp.route("/plan/task-suggestions")
class PlanTaskSuggestions(MethodView):
    @require_role(Role.VIEWER)
    @blp.arguments(PlanTasksQuerySchema, location="query")
    @blp.response(200, PlanTasksSchema)
    def get(self, args, allotment, membership):
        """Jobs the plan implies (sow, plant out, clear), and how many made earlier are stale."""
        current = _current(allotment, args["feature_id"])
        by_key = {t.key: t for t in current}
        existing = list(_existing(allotment, args["feature_id"]))
        have = {t.suggestion_key for t in existing}
        today = date.today()
        stale = sum(
            1
            for t in existing
            if t.status == TaskStatus.TODO
            and (t.suggestion_key not in by_key or _differs(t, by_key[t.suggestion_key]))
        )
        rows = [
            {
                "key": t.key,
                "title": t.title,
                "description": t.description,
                "due_date": t.due_date,
                "feature_id": t.feature_id,
                "plan_item_id": t.plan_item_id,
                "added": t.key in have,
            }
            for t in current
            if t.due_date >= today or t.key in have
        ]
        return {"stale": stale, "suggestions": add_equipment_suggestions(allotment.id, rows)}


@blp.route("/plan/tasks")
class PlanTasksAdd(MethodView):
    @require_role(Role.EDITOR)
    @blp.arguments(PlanTasksAddSchema)
    @blp.response(201, TaskSchema(many=True))
    def post(self, data, allotment, membership):
        """Make tasks from the plan: the ones named, or every one not yet made and still to come."""
        current = _current(allotment, data["feature_id"])
        wanted = data["keys"]
        if wanted is not None:
            unknown = set(wanted) - {t.key for t in current}
            if unknown:
                abort(422, message=f"Not part of the plan: {', '.join(sorted(unknown))}")
        have = {t.suggestion_key for t in _existing(allotment, None)}
        today = date.today()
        fresh = [
            t
            for t in current
            if t.key not in have
            and (t.key in wanted if wanted is not None else t.due_date >= today)
        ]
        tasks = [
            Task(
                allotment_id=allotment.id,
                created_by=membership.user_id,
                title=t.title,
                description=t.description,
                due_date=t.due_date,
                suggestion_key=t.key,
                feature_id=t.feature_id,
                plan_item_id=t.plan_item_id,
            )
            for t in fresh
        ]
        db.session.add_all(tasks)
        if data["equipment"]:
            db.session.flush()  # for the tasks' ids
            for task in tasks:
                if data["equipment"].get(task.suggestion_key):
                    set_task_equipment(
                        task, data["equipment"][task.suggestion_key], allotment, membership.user_id
                    )
        db.session.commit()
        for task in tasks:
            events.emit(
                "task.created",
                actor_id=membership.user_id,
                allotment_id=allotment.id,
                subject={"task_id": task.id, "feature_id": task.feature_id},
                payload={"title": task.title, "suggested": True},
            )
        return task_dicts(tasks)


@blp.route("/plan/tasks/sync")
class PlanTasksSync(MethodView):
    @require_role(Role.EDITOR)
    @blp.arguments(PlanTasksQuerySchema)
    @blp.response(200, PlanTasksSyncResultSchema)
    def post(self, data, allotment, membership):
        """Bring tasks still to do in line with the plan; started and finished ones are left alone.

        A task whose crop was removed, finished or skipped is deleted; the rest get the plan's
        current title and date. New jobs are not made here: they appear as suggestions.
        """
        by_key = {t.key: t for t in _current(allotment, data["feature_id"])}
        updated = removed = 0
        for task in _existing(allotment, data["feature_id"]).filter(Task.status == TaskStatus.TODO):
            want = by_key.get(task.suggestion_key)
            if want is None:
                db.session.delete(task)
                removed += 1
            elif _differs(task, want):
                task.title, task.description, task.due_date = (
                    want.title,
                    want.description,
                    want.due_date,
                )
                task.feature_id, task.plan_item_id = want.feature_id, want.plan_item_id
                updated += 1
        db.session.commit()
        events.emit(
            "plan_tasks.synced",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={"feature_id": data["feature_id"]},
            payload={"updated": updated, "removed": removed},
        )
        return {"updated": updated, "removed": removed}
