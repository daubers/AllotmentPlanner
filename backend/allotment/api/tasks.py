import calendar
from datetime import UTC, date, datetime, timedelta

from flask.views import MethodView
from flask_smorest import Blueprint, abort
from geoalchemy2.shape import to_shape
from marshmallow import ValidationError
from shapely.geometry import mapping

from .. import events
from ..extensions import db
from ..geojson import parse_geometry
from ..models import MapFeature, Membership, Role, Task, TaskStatus
from ..schemas import TaskInSchema, TaskPatchSchema, TaskQuerySchema, TaskSchema
from ..security import require_role

blp = Blueprint(
    "tasks",
    __name__,
    url_prefix="/api/v1/allotments/<int:allotment_id>/tasks",
    description="Tasks, optionally pinned to the map",
)

PRIORITY_ORDER = {"high": 0, "normal": 1, "low": 2}


def next_due(current: date, recurrence: str) -> date:
    if recurrence == "daily":
        return current + timedelta(days=1)
    if recurrence == "weekly":
        return current + timedelta(days=7)
    month = current.month % 12 + 1
    year = current.year + (current.month == 12)
    return date(year, month, min(current.day, calendar.monthrange(year, month)[1]))


def task_to_dict(task: Task, spawned: Task | None = None) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "priority": task.priority,
        "due_date": task.due_date,
        "recurrence": task.recurrence,
        "assignee_id": task.assignee_id,
        "feature_id": task.feature_id,
        "location": mapping(to_shape(task.location)) if task.location is not None else None,
        "completed_at": task.completed_at,
        "completed_by": task.completed_by,
        "created_at": task.created_at,
        "spawned_task_id": spawned.id if spawned else None,
    }


def _reject(message: str):
    db.session.rollback()
    abort(422, message=message)


def _apply(task: Task, data: dict, allotment) -> None:
    """Copy validated input onto ``task``, checking references belong to this allotment."""
    for key in ("title", "description", "priority", "status", "due_date", "recurrence"):
        if key in data:
            setattr(task, key, data[key])
    if data.get("feature_id") is not None:
        feature = db.session.get(MapFeature, data["feature_id"])
        if feature is None or feature.allotment_id != allotment.id:
            _reject("feature_id does not belong to this allotment")
    if "feature_id" in data:
        task.feature_id = data["feature_id"]
    if data.get("assignee_id") is not None:
        member = (
            db.session.query(Membership)
            .filter_by(user_id=data["assignee_id"], allotment_id=allotment.id)
            .first()
        )
        if member is None:
            _reject("assignee_id is not a member of this allotment")
    if "assignee_id" in data:
        task.assignee_id = data["assignee_id"]
    if "location" in data:
        if data["location"] is None:
            task.location = None
        else:
            try:
                if data["location"].get("type") != "Point":
                    raise ValidationError("location must be a GeoJSON Point")
                task.location = parse_geometry(data["location"])
            except ValidationError as exc:
                _reject(str(exc.messages[0] if exc.messages else exc))


def _get(allotment, task_id: int) -> Task:
    task = db.session.get(Task, task_id)
    if task is None or task.allotment_id != allotment.id:
        abort(404, message="Task not found")
    return task


@blp.route("")
class TaskList(MethodView):
    @require_role(Role.VIEWER)
    @blp.arguments(TaskQuerySchema, location="query")
    @blp.response(200, TaskSchema(many=True))
    def get(self, args, allotment, membership):
        q = db.session.query(Task).filter_by(allotment_id=allotment.id)
        if "status" in args:
            q = q.filter(Task.status == args["status"])
        if "open" in args:
            done = Task.status == TaskStatus.DONE
            q = q.filter(~done if args["open"] else done)
        if "due_on" in args:
            q = q.filter(Task.due_date == args["due_on"])
        if "due_by" in args:
            q = q.filter(Task.due_date <= args["due_by"])
        if "feature_id" in args:
            q = q.filter(Task.feature_id == args["feature_id"])
        if "assignee_id" in args:
            q = q.filter(Task.assignee_id == args["assignee_id"])
        tasks = q.order_by(Task.due_date.is_(None), Task.due_date, Task.id).all()
        tasks.sort(
            key=lambda t: PRIORITY_ORDER[t.priority]
        )  # stable: keeps date order per priority
        return [task_to_dict(t) for t in tasks]

    @require_role(Role.EDITOR)
    @blp.arguments(TaskInSchema)
    @blp.response(201, TaskSchema)
    def post(self, data, allotment, membership):
        task = Task(allotment_id=allotment.id, created_by=membership.user_id)
        _apply(task, data, allotment)
        db.session.add(task)
        db.session.commit()
        events.emit(
            "task.created",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={"task_id": task.id, "feature_id": task.feature_id},
            payload={"title": task.title},
        )
        return task_to_dict(task)


@blp.route("/<int:task_id>")
class TaskDetail(MethodView):
    @require_role(Role.VIEWER)
    @blp.response(200, TaskSchema)
    def get(self, allotment, membership, task_id):
        return task_to_dict(_get(allotment, task_id))

    @require_role(Role.EDITOR)
    @blp.arguments(TaskPatchSchema)
    @blp.response(200, TaskSchema)
    def patch(self, data, allotment, membership, task_id):
        task = _get(allotment, task_id)
        if task.status == TaskStatus.DONE and "status" in data:
            abort(409, message="Use /reopen to reopen a completed task")
        _apply(task, data, allotment)
        db.session.commit()
        events.emit(
            "task.updated",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={"task_id": task.id, "feature_id": task.feature_id},
            payload={"fields": sorted(data)},
        )
        return task_to_dict(task)

    @require_role(Role.EDITOR)
    @blp.response(204)
    def delete(self, allotment, membership, task_id):
        task = _get(allotment, task_id)
        db.session.delete(task)
        db.session.commit()
        events.emit(
            "task.deleted",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={"task_id": task_id},
        )


@blp.route("/<int:task_id>/complete")
class TaskComplete(MethodView):
    @require_role(Role.EDITOR)
    @blp.response(200, TaskSchema)
    def post(self, allotment, membership, task_id):
        """Mark done. A recurring task spawns its next occurrence."""
        task = _get(allotment, task_id)
        if task.status == TaskStatus.DONE:
            return task_to_dict(task)  # idempotent
        task.status = TaskStatus.DONE
        task.completed_at = datetime.now(UTC)
        task.completed_by = membership.user_id
        spawned = None
        if task.recurrence:
            spawned = Task(
                allotment_id=allotment.id,
                created_by=membership.user_id,
                title=task.title,
                description=task.description,
                priority=task.priority,
                recurrence=task.recurrence,
                assignee_id=task.assignee_id,
                feature_id=task.feature_id,
                location=task.location,
                due_date=next_due(task.due_date or date.today(), task.recurrence),
            )
            db.session.add(spawned)
        db.session.commit()
        events.emit(
            "task.completed",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={"task_id": task.id, "feature_id": task.feature_id},
            payload={"title": task.title, "spawned_task_id": spawned.id if spawned else None},
        )
        return task_to_dict(task, spawned)


@blp.route("/<int:task_id>/reopen")
class TaskReopen(MethodView):
    @require_role(Role.EDITOR)
    @blp.response(200, TaskSchema)
    def post(self, allotment, membership, task_id):
        task = _get(allotment, task_id)
        if task.status != TaskStatus.DONE:
            return task_to_dict(task)
        task.status = TaskStatus.TODO
        task.completed_at = None
        task.completed_by = None
        db.session.commit()
        events.emit(
            "task.reopened",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={"task_id": task.id, "feature_id": task.feature_id},
        )
        return task_to_dict(task)
