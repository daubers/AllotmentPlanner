from datetime import UTC, date, datetime

from flask.views import MethodView
from flask_smorest import Blueprint, abort
from geoalchemy2.shape import to_shape
from marshmallow import ValidationError
from shapely.geometry import mapping

from .. import events
from ..extensions import db
from ..geojson import parse_geometry
from ..models import MapFeature, Membership, Planting, Role, Task, TaskStatus, Tray
from ..schemas import (
    TaskBulkResultSchema,
    TaskBulkSchema,
    TaskEquipmentSetSchema,
    TaskInSchema,
    TaskPatchSchema,
    TaskQuerySchema,
    TaskSchema,
)
from ..security import require_role
from ..task_equipment import add_equipment_suggestions, equipment_for_tasks, set_task_equipment
from ..task_series import step

blp = Blueprint(
    "tasks",
    __name__,
    url_prefix="/api/v1/allotments/<int:allotment_id>/tasks",
    description="Tasks, optionally pinned to the map",
)

PRIORITY_ORDER = {"high": 0, "normal": 1, "low": 2}


RECURRENCE_UNITS = {"daily": "day", "weekly": "week", "monthly": "month"}


def next_due(current: date, recurrence: str) -> date:
    return step(current, 1, RECURRENCE_UNITS[recurrence])


def task_to_dict(
    task: Task, spawned: Task | None = None, equipment: list[dict] | None = None
) -> dict:
    """A task for the API. Pass ``equipment`` (see task_dicts) to avoid a query per task."""
    if equipment is None:
        equipment = equipment_for_tasks([task.id]).get(task.id, [])
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
        "tray_id": task.tray_id,
        "planting_id": task.planting_id,
        "series_id": task.series_id,
        "plan_item_id": task.plan_item_id,
        "equipment": equipment,
        "location": mapping(to_shape(task.location)) if task.location is not None else None,
        "completed_at": task.completed_at,
        "completed_by": task.completed_by,
        "created_at": task.created_at,
        "spawned_task_id": spawned.id if spawned else None,
    }


def task_dicts(tasks: list[Task]) -> list[dict]:
    """Several tasks for the API, with their equipment fetched in one query."""
    equipment = equipment_for_tasks([t.id for t in tasks])
    return [task_to_dict(t, equipment=equipment.get(t.id, [])) for t in tasks]


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
    for key, model in (("tray_id", Tray), ("planting_id", Planting)):
        if data.get(key) is not None:
            owner = db.session.get(model, data[key])
            if owner is None or owner.allotment_id != allotment.id:
                _reject(f"{key} does not belong to this allotment")
        if key in data:
            setattr(task, key, data[key])
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


def _finish(task: Task, allotment, membership) -> Task | None:
    """Mark ``task`` done; a recurring one returns its next occurrence (added, not committed).

    The next date counts from the later of the old due date and today, so finishing a daily job
    three days late does not produce one that is already overdue.
    """
    task.status = TaskStatus.DONE
    task.completed_at = datetime.now(UTC)
    task.completed_by = membership.user_id
    if not task.recurrence:
        return None
    today = date.today()
    spawned = Task(
        allotment_id=allotment.id,
        created_by=membership.user_id,
        title=task.title,
        description=task.description,
        priority=task.priority,
        recurrence=task.recurrence,
        assignee_id=task.assignee_id,
        feature_id=task.feature_id,
        tray_id=task.tray_id,
        planting_id=task.planting_id,
        location=task.location,
        due_date=next_due(max(task.due_date or today, today), task.recurrence),
    )
    db.session.add(spawned)
    return spawned


def suggestions_with_state(allotment, suggestions) -> list[dict]:
    """Suggestions as dicts, each marked ``added`` if a task already carries its key."""
    keys = [s.key for s in suggestions]
    have = set()
    if keys:
        rows = db.session.query(Task.suggestion_key).filter(
            Task.allotment_id == allotment.id, Task.suggestion_key.in_(keys)
        )
        have = {k for (k,) in rows}
    rows = [
        {
            "key": s.key,
            "title": s.title,
            "description": s.description,
            "due_date": s.due_date,
            "added": s.key in have,
        }
        for s in suggestions
    ]
    return add_equipment_suggestions(allotment.id, rows)


def add_suggested(
    allotment, membership, suggestions, equipment: dict[str, list[int]] | None = None, **place
) -> list[Task]:
    """Create a task for every suggestion not already added, all or nothing. ``place`` pins them.

    ``equipment`` maps a suggestion's key to the equipment ids to put on its task. Nothing is
    attached unless it is named here.
    """
    fresh = [s for s in suggestions_with_state(allotment, suggestions) if not s["added"]]
    tasks = [
        Task(
            allotment_id=allotment.id,
            created_by=membership.user_id,
            title=s["title"],
            description=s["description"],
            due_date=s["due_date"],
            suggestion_key=s["key"],
            **place,
        )
        for s in fresh
    ]
    db.session.add_all(tasks)
    if equipment:
        db.session.flush()  # for the tasks' ids
        for task in tasks:
            if equipment.get(task.suggestion_key):
                set_task_equipment(
                    task, equipment[task.suggestion_key], allotment, membership.user_id
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
    return tasks


def _reopen(task: Task) -> None:
    task.status = TaskStatus.TODO
    task.completed_at = None
    task.completed_by = None


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
        for key in ("feature_id", "tray_id", "planting_id", "priority"):
            if key in args:
                q = q.filter(getattr(Task, key) == args[key])
        if args.get("q"):
            like = "%" + args["q"].strip().replace("%", r"\%").replace("_", r"\_") + "%"
            q = q.filter(Task.title.ilike(like) | Task.description.ilike(like))
        if "assignee_id" in args:
            q = q.filter(Task.assignee_id == args["assignee_id"])
        tasks = q.order_by(Task.due_date.is_(None), Task.due_date, Task.id).all()
        tasks.sort(
            key=lambda t: PRIORITY_ORDER[t.priority]
        )  # stable: keeps date order per priority
        return task_dicts(tasks)

    @require_role(Role.EDITOR)
    @blp.arguments(TaskInSchema)
    @blp.response(201, TaskSchema)
    def post(self, data, allotment, membership):
        task = Task(allotment_id=allotment.id, created_by=membership.user_id)
        _apply(task, data, allotment)
        db.session.add(task)
        db.session.flush()  # for the task's id
        set_task_equipment(task, data["equipment_ids"], allotment, membership.user_id)
        db.session.commit()
        events.emit(
            "task.created",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={"task_id": task.id, "feature_id": task.feature_id},
            payload={"title": task.title},
        )
        return task_to_dict(task)


@blp.route("/bulk")
class TaskBulk(MethodView):
    @require_role(Role.EDITOR)
    @blp.arguments(TaskBulkSchema)
    @blp.response(200, TaskBulkResultSchema)
    def post(self, data, allotment, membership):
        """Complete, reopen, reschedule or delete several tasks at once (all or nothing)."""
        ids = list(dict.fromkeys(data["ids"]))
        tasks = db.session.query(Task).filter(Task.id.in_(ids), Task.allotment_id == allotment.id)
        by_id = {t.id: t for t in tasks}
        if len(by_id) != len(ids):
            abort(404, message="Task not found")
        action = data["action"]
        if action == "reschedule" and "due_date" not in data:
            abort(422, message="due_date is required to reschedule")
        done, deleted, events_to_emit = [], [], []
        for task_id in ids:
            task = by_id[task_id]
            subject = {"task_id": task.id, "feature_id": task.feature_id}
            if action == "delete":
                events_to_emit.append(("task.deleted", {"task_id": task.id}, {}))
                db.session.delete(task)
                deleted.append(task_id)
                continue
            if action == "complete" and task.status != TaskStatus.DONE:
                spawned = _finish(task, allotment, membership)
                events_to_emit.append(
                    ("task.completed", subject, {"title": task.title, "spawned": bool(spawned)})
                )
            elif action == "reopen" and task.status == TaskStatus.DONE:
                _reopen(task)
                events_to_emit.append(("task.reopened", subject, {}))
            elif action == "reschedule":
                task.due_date = data["due_date"]
                events_to_emit.append(("task.updated", subject, {"fields": ["due_date"]}))
            done.append(task)
        db.session.commit()
        for name, subject, payload in events_to_emit:
            events.emit(
                name,
                actor_id=membership.user_id,
                allotment_id=allotment.id,
                subject=subject,
                payload=payload,
            )
        return {"tasks": task_dicts(done), "deleted": deleted}


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
        if "equipment_ids" in data:
            set_task_equipment(task, data["equipment_ids"], allotment, membership.user_id)
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


@blp.route("/<int:task_id>/equipment")
class TaskEquipmentView(MethodView):
    @require_role(Role.EDITOR)
    @blp.arguments(TaskEquipmentSetSchema)
    @blp.response(200, TaskSchema)
    def put(self, data, allotment, membership, task_id):
        """Say exactly which equipment the task needs (replaces what was there)."""
        task = _get(allotment, task_id)
        set_task_equipment(task, data["equipment_ids"], allotment, membership.user_id)
        db.session.commit()
        events.emit(
            "task.updated",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={"task_id": task.id, "feature_id": task.feature_id},
            payload={"fields": ["equipment_ids"]},
        )
        return task_to_dict(task)


@blp.route("/<int:task_id>/complete")
class TaskComplete(MethodView):
    @require_role(Role.EDITOR)
    @blp.response(200, TaskSchema)
    def post(self, allotment, membership, task_id):
        """Mark done. A recurring task spawns its next occurrence."""
        task = _get(allotment, task_id)
        if task.status == TaskStatus.DONE:
            return task_to_dict(task)  # idempotent
        spawned = _finish(task, allotment, membership)
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
        _reopen(task)
        db.session.commit()
        events.emit(
            "task.reopened",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={"task_id": task.id, "feature_id": task.feature_id},
        )
        return task_to_dict(task)
