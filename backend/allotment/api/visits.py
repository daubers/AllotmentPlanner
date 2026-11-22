import secrets
from datetime import UTC, datetime, timedelta

from flask import Response, current_app
from flask.views import MethodView
from flask_smorest import Blueprint, abort

from .. import events
from ..extensions import db
from ..ics import feed_to_ics, visit_to_ics
from ..models import Allotment, Role, Task, Visit, VisitTask
from ..schemas import (
    CalendarTokenSchema,
    VisitInSchema,
    VisitPatchSchema,
    VisitSchema,
    VisitTasksSchema,
)
from ..security import require_role

blp = Blueprint(
    "visits",
    __name__,
    url_prefix="/api/v1/allotments/<int:allotment_id>/visits",
    description="Planned visits to the allotment, with pegged tasks and calendar export",
)

# Separate blueprint: the feed is fetched by calendar apps with no JWT, keyed by its token.
calendar_blp = Blueprint(
    "calendar_feed",
    __name__,
    url_prefix="/api/v1/calendar",
    description="Public .ics feed of an allotment's visits",
)

# A recent window either side of "now", so the feed isn't an ever-growing history of the past.
FEED_PAST_DAYS = 30
FEED_FUTURE_DAYS = 365


def _get(allotment, visit_id: int) -> Visit:
    visit = db.session.get(Visit, visit_id)
    if visit is None or visit.allotment_id != allotment.id:
        abort(404, message="Visit not found")
    return visit


def _tasks(allotment, task_ids) -> list[Task]:
    """The tasks, all of which must belong to this allotment (else nothing is changed)."""
    ids = list(dict.fromkeys(task_ids))
    tasks = db.session.query(Task).filter(Task.id.in_(ids), Task.allotment_id == allotment.id).all()
    if len(tasks) != len(ids):
        abort(422, message="task_ids must all belong to this allotment")
    return tasks


def _add(visit: Visit, tasks: list[Task]) -> int:
    have = {i.task_id for i in visit.tasks}
    new = [t for t in tasks if t.id not in have]
    next_position = len(visit.tasks)
    for offset, task in enumerate(new):
        visit.tasks.append(VisitTask(task_id=task.id, position=next_position + offset))
    return len(new)


def _visit_tasks(visit: Visit) -> list[Task]:
    return [db.session.get(Task, i.task_id) for i in visit.tasks]


def visit_to_dict(visit: Visit) -> dict:
    return {
        "id": visit.id,
        "title": visit.title,
        "notes": visit.notes,
        "starts_at": visit.starts_at,
        "duration_minutes": visit.duration_minutes,
        "task_ids": [t.task_id for t in visit.tasks],
        "created_at": visit.created_at,
        "updated_at": visit.updated_at,
    }


@blp.route("")
class Visits(MethodView):
    @require_role(Role.VIEWER)
    @blp.response(200, VisitSchema(many=True))
    def get(self, allotment, membership):
        """The allotment's visits, soonest first."""
        visits = (
            db.session.query(Visit)
            .filter_by(allotment_id=allotment.id)
            .order_by(Visit.starts_at)
            .all()
        )
        return [visit_to_dict(v) for v in visits]

    @require_role(Role.EDITOR)
    @blp.arguments(VisitInSchema)
    @blp.response(201, VisitSchema)
    def post(self, data, allotment, membership):
        """Plan a visit, optionally pegging some tasks to it already."""
        tasks = _tasks(allotment, data["task_ids"])
        visit = Visit(
            allotment_id=allotment.id,
            title=data["title"].strip(),
            notes=data["notes"].strip(),
            starts_at=data["starts_at"],
            duration_minutes=data["duration_minutes"],
            created_by=membership.user_id,
        )
        db.session.add(visit)
        _add(visit, tasks)
        db.session.commit()
        events.emit(
            "visit.created",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={"visit_id": visit.id},
            payload={"title": visit.title, "tasks": len(tasks)},
        )
        return visit_to_dict(visit)


@blp.route("/<int:visit_id>")
class VisitDetail(MethodView):
    @require_role(Role.VIEWER)
    @blp.response(200, VisitSchema)
    def get(self, allotment, membership, visit_id):
        return visit_to_dict(_get(allotment, visit_id))

    @require_role(Role.EDITOR)
    @blp.arguments(VisitPatchSchema)
    @blp.response(200, VisitSchema)
    def patch(self, data, allotment, membership, visit_id):
        """Update the visit's details. Tasks are managed through the /tasks endpoints."""
        visit = _get(allotment, visit_id)
        if "title" in data:
            visit.title = data["title"].strip()
        if "notes" in data:
            visit.notes = data["notes"].strip()
        if "starts_at" in data:
            visit.starts_at = data["starts_at"]
        if "duration_minutes" in data:
            visit.duration_minutes = data["duration_minutes"]
        db.session.commit()
        return visit_to_dict(visit)

    @require_role(Role.EDITOR)
    @blp.response(204)
    def delete(self, allotment, membership, visit_id):
        """Delete the visit. The tasks on it are not touched."""
        db.session.delete(_get(allotment, visit_id))
        db.session.commit()


@blp.route("/<int:visit_id>/tasks")
class VisitTasksView(MethodView):
    @require_role(Role.EDITOR)
    @blp.arguments(VisitTasksSchema)
    @blp.response(200, VisitSchema)
    def post(self, data, allotment, membership, visit_id):
        """Peg tasks to the visit; ones already there are left alone. All or nothing."""
        visit = _get(allotment, visit_id)
        added = _add(visit, _tasks(allotment, data["task_ids"]))
        db.session.commit()
        events.emit(
            "visit.tasks_added",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={"visit_id": visit.id},
            payload={"added": added},
        )
        return visit_to_dict(visit)


@blp.route("/<int:visit_id>/tasks/<int:task_id>")
class VisitTaskView(MethodView):
    @require_role(Role.EDITOR)
    @blp.response(200, VisitSchema)
    def delete(self, allotment, membership, visit_id, task_id):
        """Unpeg a task from the visit (the task itself stays)."""
        visit = _get(allotment, visit_id)
        item = next((i for i in visit.tasks if i.task_id == task_id), None)
        if item is None:
            abort(404, message="That task is not pegged to this visit")
        visit.tasks.remove(item)
        db.session.commit()
        return visit_to_dict(visit)


@blp.route("/<int:visit_id>/calendar.ics")
class VisitCalendar(MethodView):
    @require_role(Role.VIEWER)
    def get(self, allotment, membership, visit_id):
        """Download a single-event .ics for this visit."""
        visit = _get(allotment, visit_id)
        body = visit_to_ics(visit, _visit_tasks(visit))
        return Response(
            body,
            mimetype="text/calendar",
            headers={"Content-Disposition": f'attachment; filename="visit-{visit.id}.ics"'},
        )


def _feed_url(allotment: Allotment) -> str | None:
    if not allotment.calendar_token:
        return None
    public_url = current_app.config.get("PUBLIC_URL", "")
    # webcal:// tells calendar apps to treat this as a subscription, not a one-off download.
    path = f"/api/v1/calendar/{allotment.calendar_token}.ics"
    if public_url:
        return public_url.replace("https://", "webcal://").replace("http://", "webcal://") + path
    return f"webcal://{path}"


@blp.route("/calendar-token")
class CalendarToken(MethodView):
    @require_role(Role.VIEWER)
    @blp.response(200, CalendarTokenSchema)
    def get(self, allotment, membership):
        """The current feed subscribe URL, if one has been created."""
        return {"token": allotment.calendar_token, "feed_url": _feed_url(allotment)}

    @require_role(Role.EDITOR)
    @blp.response(200, CalendarTokenSchema)
    def post(self, allotment, membership):
        """Create the feed, or rotate it: the old URL stops working immediately."""
        allotment.calendar_token = secrets.token_urlsafe(32)
        db.session.commit()
        events.emit(
            "calendar_token.rotated",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
        )
        return {"token": allotment.calendar_token, "feed_url": _feed_url(allotment)}

    @require_role(Role.EDITOR)
    @blp.response(200, CalendarTokenSchema)
    def delete(self, allotment, membership):
        """Turn the feed off. A new one must be created to subscribe again."""
        allotment.calendar_token = None
        db.session.commit()
        return {"token": None, "feed_url": None}


@calendar_blp.route("/<string:token>.ics")
class CalendarFeed(MethodView):
    def get(self, token):
        """VCALENDAR of the allotment's recent and upcoming visits. The token is the secret."""
        allotment = db.session.query(Allotment).filter_by(calendar_token=token).one_or_none()
        if allotment is None:
            abort(404, message="Unknown or revoked calendar feed")
        now = datetime.now(UTC)
        visits = (
            db.session.query(Visit)
            .filter(
                Visit.allotment_id == allotment.id,
                Visit.starts_at >= now - timedelta(days=FEED_PAST_DAYS),
                Visit.starts_at <= now + timedelta(days=FEED_FUTURE_DAYS),
            )
            .order_by(Visit.starts_at)
            .all()
        )
        body = feed_to_ics([(v, _visit_tasks(v)) for v in visits])
        return Response(body, mimetype="text/calendar")
