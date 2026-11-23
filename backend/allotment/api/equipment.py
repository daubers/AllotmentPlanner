from datetime import date

from flask.views import MethodView
from flask_jwt_extended import jwt_required
from flask_smorest import Blueprint, abort
from sqlalchemy import func, or_

from .. import events
from ..equipment_kinds import KINDS, kind_label, parse_keywords
from ..extensions import db
from ..models import Equipment, MapFeature, Role, Task, TaskSeries, TaskStatus
from ..schemas import (
    EquipmentInSchema,
    EquipmentKindSchema,
    EquipmentPatchSchema,
    EquipmentQuerySchema,
    EquipmentSchema,
    EquipmentSuggestInSchema,
    EquipmentSuggestionSchema,
    MaintenanceInSchema,
    MaintenanceSchema,
    TaskSeriesSchema,
)
from ..security import require_role
from ..task_equipment import feature_kinds, load_equipment, suggest_equipment
from ..visit_bring import touch_visits_for_equipment
from .task_series import create_series, drop_future_todo, series_to_dict

blp = Blueprint(
    "equipment",
    __name__,
    url_prefix="/api/v1/allotments/<int:allotment_id>/equipment",
    description="Tools and equipment you own",
)
kinds_blp = Blueprint(
    "equipment_kinds",
    __name__,
    url_prefix="/api/v1/equipment-kinds",
    description="The kinds of equipment the app knows about",
)

FIELDS = (
    "name",
    "kind",
    "quantity",
    "notes",
    "used_for",
    "status",
    "location_feature_id",
    "last_serviced_on",
)


def maintenance_summary(ids: list[int]) -> dict[int, tuple[date | None, int]]:
    """For each item with maintenance still to do: (earliest due date, job count), one query."""
    if not ids:
        return {}
    rows = (
        db.session.query(Task.equipment_id, func.min(Task.due_date), func.count(Task.id))
        .filter(Task.equipment_id.in_(ids), Task.status != TaskStatus.DONE)
        .group_by(Task.equipment_id)
    )
    return {eid: (due, n) for eid, due, n in rows}


def equipment_to_dict(
    item: Equipment,
    locations: dict[int, str] | None = None,
    summary: dict[int, tuple[date | None, int]] | None = None,
) -> dict:
    if locations is None:
        locations = _locations([item])
    if summary is None:
        summary = maintenance_summary([item.id])
    next_due, open_tasks = summary.get(item.id, (None, 0))
    return {
        "id": item.id,
        "name": item.name,
        "kind": item.kind,
        "kind_label": kind_label(item.kind),
        "quantity": item.quantity,
        "notes": item.notes,
        "used_for": item.used_for,
        "keywords": parse_keywords(item.used_for),
        "status": item.status,
        "location_feature_id": item.location_feature_id,
        "location_name": locations.get(item.location_feature_id),
        "last_serviced_on": item.last_serviced_on,
        "next_due": next_due,
        "overdue": next_due is not None and next_due < date.today(),
        "maintenance_tasks": open_tasks,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _locations(items: list[Equipment]) -> dict[int, str]:
    """Names of the places the items live, in one query."""
    ids = {i.location_feature_id for i in items if i.location_feature_id}
    if not ids:
        return {}
    rows = db.session.query(MapFeature.id, MapFeature.name).filter(MapFeature.id.in_(ids))
    return {fid: name or f"Feature {fid}" for fid, name in rows}


def _get(allotment, equipment_id: int) -> Equipment:
    item = db.session.get(Equipment, equipment_id)
    if item is None or item.allotment_id != allotment.id:
        abort(404, message="Equipment not found")
    return item


def _check_location(allotment, feature_id: int | None) -> None:
    if feature_id is not None:
        feature = db.session.get(MapFeature, feature_id)
        if feature is None or feature.allotment_id != allotment.id:
            abort(422, message="location_feature_id does not belong to this allotment")


def _emit(action: str, allotment, membership, item: Equipment, **payload) -> None:
    events.emit(
        f"equipment.{action}",
        actor_id=membership.user_id,
        allotment_id=allotment.id,
        subject={"equipment_id": item.id},
        payload={"name": item.name, **payload},
    )


@kinds_blp.route("")
class Kinds(MethodView):
    @jwt_required()
    @kinds_blp.response(200, EquipmentKindSchema(many=True))
    def get(self):
        """The kinds an item can be, for choosing one."""
        return [{"key": key, "label": label} for key, label in KINDS.items()]


@blp.route("")
class EquipmentList(MethodView):
    @require_role(Role.VIEWER)
    @blp.arguments(EquipmentQuerySchema, location="query")
    @blp.response(200, EquipmentSchema(many=True))
    def get(self, args, allotment, membership):
        rows = db.session.query(Equipment).filter_by(allotment_id=allotment.id)
        if args.get("kind"):
            rows = rows.filter(Equipment.kind == args["kind"])
        if args.get("status"):
            rows = rows.filter(Equipment.status == args["status"])
        if args.get("q", "").strip():
            like = f"%{args['q'].strip()}%"
            rows = rows.filter(
                or_(
                    Equipment.name.ilike(like),
                    Equipment.notes.ilike(like),
                    Equipment.used_for.ilike(like),
                )
            )
        items = rows.order_by(db.func.lower(Equipment.name), Equipment.id).all()
        locations = _locations(items)
        summary = maintenance_summary([i.id for i in items])
        return [equipment_to_dict(i, locations, summary) for i in items]

    @require_role(Role.EDITOR)
    @blp.arguments(EquipmentInSchema)
    @blp.response(201, EquipmentSchema)
    def post(self, data, allotment, membership):
        _check_location(allotment, data["location_feature_id"])
        item = Equipment(allotment_id=allotment.id, created_by=membership.user_id, **data)
        db.session.add(item)
        db.session.commit()
        _emit("created", allotment, membership, item, kind=item.kind)
        return equipment_to_dict(item)


@blp.route("/suggest")
class EquipmentSuggest(MethodView):
    @require_role(Role.VIEWER)
    @blp.arguments(EquipmentSuggestInSchema)
    @blp.response(200, EquipmentSuggestionSchema(many=True))
    def post(self, data, allotment, membership):
        """Which of your equipment a job probably needs, from its wording and where it is."""
        items, by_id = load_equipment(allotment.id)
        feature_kind = None
        if data["feature_id"] is not None:
            feature_kind = feature_kinds({data["feature_id"]}).get(data["feature_id"])
        return suggest_equipment(
            items,
            by_id,
            title=data["title"],
            description=data["description"],
            key=data["suggestion_key"],
            feature_kind=feature_kind,
            exclude=set(data["exclude_ids"]),
        )


@blp.route("/<int:equipment_id>/maintenance")
class EquipmentMaintenance(MethodView):
    @require_role(Role.VIEWER)
    @blp.response(200, MaintenanceSchema)
    def get(self, allotment, membership, equipment_id):
        """The maintenance schedules on this item, when it is next due and when it was last done."""
        item = _get(allotment, equipment_id)
        schedules = (
            db.session.query(TaskSeries)
            .filter_by(equipment_id=item.id)
            .order_by(TaskSeries.starts_on, TaskSeries.id)
        )
        next_due, open_tasks = maintenance_summary([item.id]).get(item.id, (None, 0))
        return {
            "schedules": [series_to_dict(s) for s in schedules],
            "next_due": next_due,
            "overdue": next_due is not None and next_due < date.today(),
            "open_tasks": open_tasks,
            "last_serviced_on": item.last_serviced_on,
        }

    @require_role(Role.EDITOR)
    @blp.arguments(MaintenanceInSchema)
    @blp.response(201, TaskSeriesSchema)
    def post(self, data, allotment, membership, equipment_id):
        """Schedule maintenance: every so often until a date, or once (starts_on = until_on).

        Each occurrence becomes an ordinary task about this item, from today on.
        """
        item = _get(allotment, equipment_id)
        data = {**data, "title": data["title"].strip() or f"Service {item.name}"}
        return create_series(allotment, membership, data, equipment_id=item.id)


@blp.route("/<int:equipment_id>")
class EquipmentDetail(MethodView):
    @require_role(Role.VIEWER)
    @blp.response(200, EquipmentSchema)
    def get(self, allotment, membership, equipment_id):
        return equipment_to_dict(_get(allotment, equipment_id))

    @require_role(Role.EDITOR)
    @blp.arguments(EquipmentPatchSchema)
    @blp.response(200, EquipmentSchema)
    def patch(self, data, allotment, membership, equipment_id):
        item = _get(allotment, equipment_id)
        if "location_feature_id" in data:
            _check_location(allotment, data["location_feature_id"])
        for key in FIELDS:
            if key in data:
                setattr(item, key, data[key])
        touch_visits_for_equipment(item.id)  # its name or status shows on visits' bring lists
        db.session.commit()
        _emit("updated", allotment, membership, item, fields=sorted(data))
        return equipment_to_dict(item)

    @require_role(Role.EDITOR)
    @blp.response(204)
    def delete(self, allotment, membership, equipment_id):
        item = _get(allotment, equipment_id)
        name = item.name
        touch_visits_for_equipment(item.id)  # before the links go with it
        # Its maintenance schedules end with it: jobs still to do go, finished ones stay as history.
        for series in db.session.query(TaskSeries).filter_by(equipment_id=item.id).all():
            drop_future_todo(series, date.today())
            db.session.delete(series)
        db.session.flush()
        db.session.delete(item)
        db.session.commit()
        events.emit(
            "equipment.deleted",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={"equipment_id": equipment_id},
            payload={"name": name},
        )
