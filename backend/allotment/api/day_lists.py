from datetime import date

from flask.views import MethodView
from flask_smorest import Blueprint, abort

from .. import events
from ..extensions import db
from ..geojson import feature_to_geojson
from ..models import DayList, DayListItem, MapFeature, Role, Task, TaskStatus
from ..schemas import (
    DayListInSchema,
    DayListPatchSchema,
    DayListSchema,
    DayListTasksSchema,
    TodoSchema,
)
from ..security import require_role
from .tasks import PRIORITY_ORDER, task_dicts

blp = Blueprint(
    "day_lists",
    __name__,
    url_prefix="/api/v1/allotments/<int:allotment_id>/day-lists",
    description="Hand-picked lists of tasks, shown as a todo sheet",
)


def _get(allotment, list_id: int) -> DayList:
    day_list = db.session.get(DayList, list_id)
    if day_list is None or day_list.allotment_id != allotment.id:
        abort(404, message="Day list not found")
    return day_list


def _tasks(allotment, task_ids) -> list[Task]:
    """The tasks, all of which must belong to this allotment (else nothing is changed)."""
    ids = list(dict.fromkeys(task_ids))
    tasks = db.session.query(Task).filter(Task.id.in_(ids), Task.allotment_id == allotment.id).all()
    if len(tasks) != len(ids):
        abort(422, message="task_ids must all belong to this allotment")
    return tasks


def _add(day_list: DayList, tasks: list[Task]) -> int:
    have = {i.task_id for i in day_list.items}
    new = [t for t in tasks if t.id not in have]
    for task in new:
        day_list.items.append(DayListItem(task_id=task.id))
    return len(new)


def list_to_dict(day_list: DayList) -> dict:
    tasks = [db.session.get(Task, i.task_id) for i in day_list.items]
    return {
        "id": day_list.id,
        "name": day_list.name,
        "date": day_list.for_date,
        "task_ids": [t.id for t in tasks],
        "task_count": len(tasks),
        "done_count": sum(t.status == TaskStatus.DONE for t in tasks),
        "created_at": day_list.created_at,
    }


@blp.route("")
class DayLists(MethodView):
    @require_role(Role.VIEWER)
    @blp.response(200, DayListSchema(many=True))
    def get(self, allotment, membership):
        """The allotment's day lists, newest first."""
        lists = (
            db.session.query(DayList)
            .filter_by(allotment_id=allotment.id)
            .order_by(DayList.id.desc())
            .all()
        )
        return [list_to_dict(d) for d in lists]

    @require_role(Role.EDITOR)
    @blp.arguments(DayListInSchema)
    @blp.response(201, DayListSchema)
    def post(self, data, allotment, membership):
        """Make a list, optionally with some tasks already on it."""
        tasks = _tasks(allotment, data["task_ids"])
        day_list = DayList(
            allotment_id=allotment.id,
            name=data["name"].strip(),
            for_date=data["date"],
            created_by=membership.user_id,
        )
        db.session.add(day_list)
        _add(day_list, tasks)
        db.session.commit()
        events.emit(
            "daylist.created",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={"day_list_id": day_list.id},
            payload={"name": day_list.name, "tasks": len(tasks)},
        )
        return list_to_dict(day_list)


@blp.route("/<int:list_id>")
class DayListItemView(MethodView):
    @require_role(Role.VIEWER)
    @blp.response(200, DayListSchema)
    def get(self, allotment, membership, list_id):
        return list_to_dict(_get(allotment, list_id))

    @require_role(Role.EDITOR)
    @blp.arguments(DayListPatchSchema)
    @blp.response(200, DayListSchema)
    def patch(self, data, allotment, membership, list_id):
        """Rename the list or change its date (null clears it)."""
        day_list = _get(allotment, list_id)
        if "name" in data:
            day_list.name = data["name"].strip()
        if "date" in data:
            day_list.for_date = data["date"]
        db.session.commit()
        return list_to_dict(day_list)

    @require_role(Role.EDITOR)
    @blp.response(204)
    def delete(self, allotment, membership, list_id):
        """Delete the list. The tasks on it are not touched."""
        db.session.delete(_get(allotment, list_id))
        db.session.commit()


@blp.route("/<int:list_id>/tasks")
class DayListTasks(MethodView):
    @require_role(Role.EDITOR)
    @blp.arguments(DayListTasksSchema)
    @blp.response(200, DayListSchema)
    def post(self, data, allotment, membership, list_id):
        """Put tasks on the list; ones already there are left alone. All or nothing."""
        day_list = _get(allotment, list_id)
        added = _add(day_list, _tasks(allotment, data["task_ids"]))
        db.session.commit()
        events.emit(
            "daylist.tasks_added",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={"day_list_id": day_list.id},
            payload={"added": added},
        )
        return list_to_dict(day_list)


@blp.route("/<int:list_id>/tasks/<int:task_id>")
class DayListTask(MethodView):
    @require_role(Role.EDITOR)
    @blp.response(200, DayListSchema)
    def delete(self, allotment, membership, list_id, task_id):
        """Take a task off the list (the task itself stays)."""
        day_list = _get(allotment, list_id)
        item = next((i for i in day_list.items if i.task_id == task_id), None)
        if item is None:
            abort(404, message="That task is not on the list")
        day_list.items.remove(item)
        db.session.commit()
        return list_to_dict(day_list)


@blp.route("/<int:list_id>/todo")
class DayListSheet(MethodView):
    @require_role(Role.VIEWER)
    @blp.response(200, TodoSchema)
    def get(self, allotment, membership, list_id):
        """The todo sheet for this list. Done tasks stay on it so a ticked job is not lost."""
        day_list = _get(allotment, list_id)
        tasks = [db.session.get(Task, i.task_id) for i in day_list.items]
        tasks.sort(key=lambda t: (t.status == TaskStatus.DONE, PRIORITY_ORDER[t.priority]))
        features = (
            db.session.query(MapFeature)
            .filter_by(allotment_id=allotment.id)
            .order_by(MapFeature.id)
        )
        return {
            "date": day_list.for_date or date.today(),
            "allotment": {"id": allotment.id, "name": allotment.name},
            "tasks": task_dicts(tasks),
            "features": [feature_to_geojson(f) for f in features],
            "members": [
                {"user_id": m.user_id, "display_name": m.user.display_name}
                for m in allotment.memberships
            ],
            "title": day_list.name,
        }
