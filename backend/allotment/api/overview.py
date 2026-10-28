from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from flask.views import MethodView
from flask_smorest import Blueprint

from ..extensions import db
from ..models import ActivityLog, Media, Role, Task, TaskStatus
from ..schemas import OverviewQuerySchema, OverviewSchema
from ..security import require_role
from .media import media_to_dict

blp = Blueprint(
    "overview",
    __name__,
    url_prefix="/api/v1/allotments/<int:allotment_id>/overview",
    description="Progress overview: what got done, and when",
)

# Event type -> overview counter. Anything unlisted is not part of the story.
COUNTERS = {
    "task.completed": "tasks_done",
    "task.created": "tasks_added",
    "media.uploaded": "photos_added",
    "feature.created": "map_edits",
    "feature.updated": "map_edits",
    "feature.deleted": "map_edits",
    "feature.bulk_replaced": "map_edits",
    "layer.created": "map_edits",
}
FIELDS = ("tasks_done", "tasks_added", "photos_added", "map_edits")
# A day counts towards a streak if real work happened (planning alone doesn't).
STREAK_FIELDS = ("tasks_done", "photos_added", "map_edits")


def _blank() -> dict:
    return dict.fromkeys(FIELDS, 0)


def _sum(days: list[dict]) -> dict:
    out = {f: sum(d[f] for d in days) for f in FIELDS}
    out["active_days"] = sum(1 for d in days if d["total"] > 0)
    return out


def _streaks(active: set[date], today: date) -> dict:
    longest = run = 0
    prev = None
    for day in sorted(active):
        run = run + 1 if prev is not None and day - prev == timedelta(days=1) else 1
        longest = max(longest, run)
        prev = day
    # Today may not have happened yet, so a streak that ended yesterday is still alive.
    cursor = today if today in active else today - timedelta(days=1)
    current = 0
    while cursor in active:
        current += 1
        cursor -= timedelta(days=1)
    return {"current": current, "longest": longest}


def build_overview(allotment, days: int, today: date) -> dict:
    rows = (
        db.session.query(ActivityLog.type, ActivityLog.occurred_at, ActivityLog.payload)
        .filter(ActivityLog.allotment_id == allotment.id, ActivityLog.type.in_(COUNTERS))
        .all()
    )
    per_day: dict[date, dict] = defaultdict(_blank)
    for type_, at, payload in rows:
        n = 1
        if type_ == "feature.bulk_replaced":  # one save can touch many features
            n = sum((payload or {}).get(k, 0) for k in ("created", "updated", "deleted")) or 1
        per_day[at.astimezone(UTC).date()][COUNTERS[type_]] += n

    def day_row(day: date) -> dict:
        row = {"date": day, **per_day.get(day, _blank())}
        row["total"] = sum(row[f] for f in FIELDS)
        return row

    window = [day_row(today - timedelta(days=i)) for i in range(days - 1, -1, -1)]
    monday = today - timedelta(days=today.weekday())
    this_week = [day_row(monday + timedelta(days=i)) for i in range(7)]
    last_week = [day_row(monday - timedelta(days=7) + timedelta(days=i)) for i in range(7)]
    all_rows = [day_row(d) for d in per_day]
    active = {r["date"] for r in all_rows if any(r[f] for f in STREAK_FIELDS)}

    photos = (
        db.session.query(Media)
        .filter_by(allotment_id=allotment.id, kind="photo", status="ready")
        .order_by(Media.taken_at.desc(), Media.id.desc())
        .limit(8)
        .all()
    )
    done = (
        db.session.query(Task)
        .filter(Task.allotment_id == allotment.id, Task.status == TaskStatus.DONE)
        .order_by(Task.completed_at.desc())
        .limit(8)
        .all()
    )
    return {
        "days": window,
        "this_week": _sum(this_week),
        "last_week": _sum(last_week),
        "totals": _sum(all_rows),
        "streak": _streaks(active, today),
        "open_tasks": db.session.query(Task)
        .filter(Task.allotment_id == allotment.id, Task.status != TaskStatus.DONE)
        .count(),
        "recent_photos": [media_to_dict(m) for m in photos],
        "recent_done": [
            {"id": t.id, "title": t.title, "completed_at": t.completed_at.isoformat()}
            for t in done
            if t.completed_at
        ],
    }


@blp.route("")
class Overview(MethodView):
    @require_role(Role.VIEWER)
    @blp.arguments(OverviewQuerySchema, location="query")
    @blp.response(200, OverviewSchema)
    def get(self, args, allotment, membership):
        """Per-day activity counts, weekly comparison, streaks and the newest photos."""
        today = args.get("today") or datetime.now(UTC).date()
        return build_overview(allotment, args["days"], today)
