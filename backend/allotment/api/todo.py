from datetime import date

from flask.views import MethodView
from flask_smorest import Blueprint

from ..extensions import db
from ..geojson import feature_to_geojson
from ..models import MapFeature, Role, Task, TaskStatus
from ..schemas import TodoQuerySchema, TodoSchema
from ..security import require_role
from .tasks import PRIORITY_ORDER, task_to_dict

blp = Blueprint(
    "todo",
    __name__,
    url_prefix="/api/v1/allotments/<int:allotment_id>/todo",
    description="The printable day plan",
)


@blp.route("")
class Todo(MethodView):
    @require_role(Role.VIEWER)
    @blp.arguments(TodoQuerySchema, location="query")
    @blp.response(200, TodoSchema)
    def get(self, args, allotment, membership):
        """Everything open that is due on or before ``date`` (so overdue jobs are included)."""
        day = args.get("date") or date.today()
        due = Task.due_date <= day
        if args["include_undated"]:
            due = due | Task.due_date.is_(None)
        tasks = (
            db.session.query(Task)
            .filter(Task.allotment_id == allotment.id, Task.status != TaskStatus.DONE, due)
            .order_by(Task.due_date.is_(None), Task.due_date, Task.id)
            .all()
        )
        tasks.sort(key=lambda t: PRIORITY_ORDER[t.priority])
        features = (
            db.session.query(MapFeature)
            .filter_by(allotment_id=allotment.id)
            .order_by(MapFeature.id)
        )
        return {
            "date": day,
            "allotment": {"id": allotment.id, "name": allotment.name},
            "tasks": [task_to_dict(t) for t in tasks],
            "features": [feature_to_geojson(f) for f in features],
            "members": [
                {"user_id": m.user_id, "display_name": m.user.display_name}
                for m in allotment.memberships
            ],
        }
