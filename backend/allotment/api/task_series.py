from datetime import date

from flask.views import MethodView
from flask_smorest import Blueprint, abort
from sqlalchemy import func

from .. import events
from ..extensions import db
from ..models import MapFeature, Membership, Role, Task, TaskSeries, TaskStatus
from ..schemas import TaskSeriesInSchema, TaskSeriesPatchSchema, TaskSeriesSchema
from ..security import require_role
from ..task_series import describe, occurrence_key, occurrences

blp = Blueprint(
    "task_series",
    __name__,
    url_prefix="/api/v1/allotments/<int:allotment_id>/task-series",
    description="Jobs that repeat on a schedule, created ahead as ordinary tasks",
)

EDITABLE = (
    "title",
    "description",
    "priority",
    "assignee_id",
    "feature_id",
    "every_n",
    "unit",
    "starts_on",
    "until_on",
)


def series_to_dict(series: TaskSeries) -> dict:
    tasks = db.session.query(Task).filter_by(series_id=series.id)
    open_tasks = tasks.filter(Task.status != TaskStatus.DONE)
    return {
        "id": series.id,
        "title": series.title,
        "description": series.description,
        "priority": series.priority,
        "assignee_id": series.assignee_id,
        "feature_id": series.feature_id,
        "equipment_id": series.equipment_id,
        "every_n": series.every_n,
        "unit": series.unit,
        "starts_on": series.starts_on,
        "until_on": series.until_on,
        "rule": describe(series.every_n, series.unit),
        "open_tasks": open_tasks.count(),
        "done_tasks": tasks.filter(Task.status == TaskStatus.DONE).count(),
        "next_due": open_tasks.with_entities(func.min(Task.due_date)).scalar(),
        "created_at": series.created_at,
    }


def _get(allotment, series_id: int) -> TaskSeries:
    series = db.session.get(TaskSeries, series_id)
    if series is None or series.allotment_id != allotment.id:
        abort(404, message="Series not found")
    return series


def _check_refs(allotment, assignee_id, feature_id) -> None:
    if feature_id is not None:
        feature = db.session.get(MapFeature, feature_id)
        if feature is None or feature.allotment_id != allotment.id:
            abort(422, message="feature_id does not belong to this allotment")
    if assignee_id is not None:
        member = (
            db.session.query(Membership)
            .filter_by(user_id=assignee_id, allotment_id=allotment.id)
            .first()
        )
        if member is None:
            abort(422, message="assignee_id is not a member of this allotment")


def _reject(message: str):
    db.session.rollback()  # drop any edit already made to the series
    abort(422, message=message)


def _dates(series: TaskSeries, today: date) -> list[date]:
    if series.until_on < series.starts_on:
        _reject("The series ends before it starts")
    try:
        return occurrences(
            series.starts_on, series.until_on, series.every_n, series.unit, not_before=today
        )
    except ValueError as exc:
        _reject(f"{exc}. Shorten the period or repeat it less often")


def _fill(series: TaskSeries, dates: list[date], created_by: int) -> None:
    """Create the occurrence for each date that does not have one yet (done ones keep theirs)."""
    have = {
        k
        for (k,) in db.session.query(Task.suggestion_key).filter(
            Task.allotment_id == series.allotment_id,
            Task.suggestion_key.like(f"series:{series.id}:%"),
        )
    }
    db.session.add_all(
        Task(
            allotment_id=series.allotment_id,
            created_by=created_by,
            title=series.title,
            description=series.description,
            priority=series.priority,
            assignee_id=series.assignee_id,
            feature_id=series.feature_id,
            equipment_id=series.equipment_id,
            due_date=d,
            series_id=series.id,
            suggestion_key=occurrence_key(series.id, d),
        )
        for d in dates
        if occurrence_key(series.id, d) not in have
    )


def drop_future_todo(series: TaskSeries, today: date) -> None:
    """Remove occurrences not yet started and still due; done and started ones stay."""
    db.session.query(Task).filter(
        Task.series_id == series.id, Task.status == TaskStatus.TODO, Task.due_date >= today
    ).delete(synchronize_session=False)


def create_series(allotment, membership, data: dict, equipment_id: int | None = None) -> dict:
    """Make a series and its occurrences from now on (committed); returns it for the API.

    ``equipment_id`` marks it as maintenance of that equipment (the caller has checked it).
    """
    _check_refs(allotment, data.get("assignee_id"), data.get("feature_id"))
    series = TaskSeries(
        allotment_id=allotment.id,
        created_by=membership.user_id,
        equipment_id=equipment_id,
        **{k: v for k, v in data.items() if k in EDITABLE},
    )
    dates = _dates(series, date.today())
    db.session.add(series)
    db.session.flush()
    _fill(series, dates, membership.user_id)
    db.session.commit()
    events.emit(
        "task_series.created",
        actor_id=membership.user_id,
        allotment_id=allotment.id,
        subject={"series_id": series.id, "feature_id": series.feature_id},
        payload={"title": series.title, "occurrences": len(dates), "equipment_id": equipment_id},
    )
    return series_to_dict(series)


@blp.route("")
class SeriesList(MethodView):
    @require_role(Role.VIEWER)
    @blp.response(200, TaskSeriesSchema(many=True))
    def get(self, allotment, membership):
        rows = (
            db.session.query(TaskSeries)
            .filter_by(allotment_id=allotment.id)
            .order_by(TaskSeries.starts_on, TaskSeries.id)
        )
        return [series_to_dict(s) for s in rows]

    @require_role(Role.EDITOR)
    @blp.arguments(TaskSeriesInSchema)
    @blp.response(201, TaskSeriesSchema)
    def post(self, data, allotment, membership):
        """Repeat a job. Occurrences from today to the end date become tasks straight away."""
        return create_series(allotment, membership, data)


@blp.route("/<int:series_id>")
class SeriesDetail(MethodView):
    @require_role(Role.VIEWER)
    @blp.response(200, TaskSeriesSchema)
    def get(self, allotment, membership, series_id):
        return series_to_dict(_get(allotment, series_id))

    @require_role(Role.EDITOR)
    @blp.arguments(TaskSeriesPatchSchema)
    @blp.response(200, TaskSeriesSchema)
    def patch(self, data, allotment, membership, series_id):
        """Change the rule or details. Occurrences still to come are remade; done ones are kept."""
        series = _get(allotment, series_id)
        _check_refs(
            allotment,
            data.get("assignee_id", series.assignee_id),
            data.get("feature_id", series.feature_id),
        )
        for key in EDITABLE:
            if key in data:
                setattr(series, key, data[key])
        today = date.today()
        dates = _dates(series, today)  # refuses a bad rule before anything is deleted
        drop_future_todo(series, today)
        _fill(series, dates, membership.user_id)
        db.session.commit()
        events.emit(
            "task_series.updated",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={"series_id": series.id, "feature_id": series.feature_id},
            payload={"fields": sorted(data)},
        )
        return series_to_dict(series)

    @require_role(Role.EDITOR)
    @blp.response(204)
    def delete(self, allotment, membership, series_id):
        """Stop the series. Occurrences still to do are removed; finished and started ones stay."""
        series = _get(allotment, series_id)
        drop_future_todo(series, date.today())
        db.session.delete(series)
        db.session.commit()
        events.emit(
            "task_series.deleted",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={"series_id": series_id},
        )
