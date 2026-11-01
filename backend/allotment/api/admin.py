"""The admin page's data: how the workers and queues are doing, recent jobs, and the stored logs."""

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import redis
import structlog
from celery.schedules import crontab
from flask import current_app
from flask.views import MethodView
from flask_smorest import Blueprint
from sqlalchemy import func, text

from ..celery_app import celery
from ..extensions import db
from ..models import Allotment, LogEntry, MapJob, MastodonPost, PacketScan, User
from ..schemas import JobsSchema, LogQuerySchema, LogsSchema, SystemSchema, WorkersSchema
from ..security import require_admin
from ..storage import get_storage

blp = Blueprint(
    "admin",
    __name__,
    url_prefix="/api/v1/admin",
    description="Worker state, jobs and logs (site admins only)",
)
log = structlog.get_logger(__name__)

# Every queue a task can be routed to (see task_routes in celery_app): the default one plus these.
QUEUES = ["celery", "mapping", "vision"]
LEVEL_ORDER = ["info", "warning", "error", "critical"]
INSPECT_TIMEOUT = 1.5


def describe_schedule(schedule) -> str:
    if isinstance(schedule, int | float):
        seconds = int(schedule)
        return f"every {seconds // 60} min" if seconds % 60 == 0 else f"every {seconds} s"
    if isinstance(schedule, crontab):
        hours, minutes = sorted(schedule.hour), sorted(schedule.minute)
        if len(hours) == 1 and len(minutes) == 1:
            return f"daily at {hours[0]:02d}:{minutes[0]:02d} UTC"
    return str(schedule)


def collect_workers(
    stats=None, active=None, reserved=None, queues=None, info=None, now: float | None = None
) -> list[dict]:
    """Join the answers to Celery's inspect calls (each a dict keyed by node name, or None)."""
    now = time.time() if now is None else now
    stats, active, reserved = stats or {}, active or {}, reserved or {}
    queues, info = queues or {}, info or {}
    workers = []
    for name in sorted(set(stats) | set(active) | set(queues) | set(info)):
        s = stats.get(name) or {}
        extra = info.get(name) or {}
        workers.append(
            {
                "name": name,
                "queues": sorted(q["name"] for q in queues.get(name) or []),
                "concurrency": (s.get("pool") or {}).get("max-concurrency"),
                "pid": s.get("pid"),
                "uptime_seconds": s.get("uptime"),
                "processed": sum((s.get("total") or {}).values()) if s.get("total") else 0,
                "reserved": len(reserved.get(name) or []),
                "active": [
                    {
                        "id": t.get("id"),
                        "name": t.get("name"),
                        "running_seconds": round(now - t["time_start"], 1)
                        if t.get("time_start")
                        else None,
                    }
                    for t in active.get(name) or []
                ],
                "version": extra.get("version"),
                "gpu": extra.get("gpu"),
            }
        )
    return workers


def _inspect() -> dict:
    """Ask every worker about itself. The calls run side by side: each waits out the timeout."""
    inspector = celery.control.inspect(timeout=INSPECT_TIMEOUT)
    calls = {
        "stats": inspector.stats,
        "active": inspector.active,
        "reserved": inspector.reserved,
        "queues": inspector.active_queues,
        "info": lambda: inspector._request("allotment_info"),
    }
    with ThreadPoolExecutor(max_workers=len(calls)) as pool:
        futures = {key: pool.submit(call) for key, call in calls.items()}
        return {key: future.result() for key, future in futures.items()}


def _queue_depths() -> dict[str, int | None]:
    try:
        client = redis.Redis.from_url(current_app.config["REDIS_URL"], socket_timeout=2)
        return {name: int(client.llen(name)) for name in QUEUES}
    except Exception:  # noqa: BLE001 - shown as "unknown"
        return {name: None for name in QUEUES}


def _beat_entries() -> list[dict]:
    entries = []
    for name, entry in sorted(celery.conf.beat_schedule.items()):
        last = (
            LogEntry.query.filter(
                LogEntry.event == "task.finished",
                LogEntry.data["task"].as_string() == entry["task"],
            )
            .order_by(LogEntry.id.desc())
            .first()
        )
        entries.append(
            {
                "name": name,
                "task": entry["task"],
                "schedule": describe_schedule(entry["schedule"]),
                "last_run": last.at if last else None,
                "last_state": (last.data or {}).get("state") if last else None,
            }
        )
    return entries


@blp.route("/workers")
class Workers(MethodView):
    @require_admin
    @blp.response(200, WorkersSchema)
    def get(self):
        """Which workers are online, what they are doing, how long the queues are, the schedule."""
        error = None
        try:
            answers = _inspect()
        except Exception as exc:  # noqa: BLE001 - the broker being down is the thing to show
            log.warning("admin.inspect_failed", error=str(exc))
            answers, error = {}, f"Could not reach the broker: {exc.__class__.__name__}"
        workers = collect_workers(**answers)
        depths = _queue_depths()
        queues = [
            {
                "name": name,
                "depth": depths.get(name),
                "consumers": sum(name in w["queues"] for w in workers),
            }
            for name in QUEUES
        ]
        return {
            "workers": workers,
            "queues": queues,
            "beat": _beat_entries(),
            "error": error,
            "checked_at": datetime.now(UTC),
        }


def _check(fn) -> str:
    try:
        fn()
        return "ok"
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc.__class__.__name__}"


@blp.route("/system")
class System(MethodView):
    @require_admin
    @blp.response(200, SystemSchema)
    def get(self):
        """Is everything the app depends on reachable, and which version is running."""
        checks = {
            "database": _check(lambda: db.session.execute(text("SELECT 1"))),
            "redis": _check(
                lambda: redis.Redis.from_url(
                    current_app.config["REDIS_URL"], socket_timeout=2
                ).ping()
            ),
            "storage": _check(lambda: get_storage().get_bytes("admin-health-probe")),
        }
        return {
            "version": current_app.config["APP_VERSION"],
            "server_time": datetime.now(UTC),
            "checks": checks,
            "users": db.session.query(func.count(User.id)).scalar(),
            "allotments": db.session.query(func.count(Allotment.id)).scalar(),
            "log_rows": db.session.query(func.count(LogEntry.id)).scalar(),
            "log_retention_days": current_app.config["LOG_RETENTION_DAYS"],
        }


def _jobs() -> tuple[list[dict], list[dict]]:
    day_ago = datetime.now(UTC) - timedelta(days=1)
    kinds = {
        "map": (MapJob, ("queued", "running"), "failed", lambda j: j.name),
        "scan": (PacketScan, ("queued", "running"), "failed", lambda j: f"Packet photo {j.id}"),
        "mastodon": (
            MastodonPost,
            ("pending", "sending"),
            "failed",
            lambda j: f"{j.kind} post",
        ),
    }
    jobs, counts = [], []
    for kind, (model, waiting, failed, label) in kinds.items():
        rows = model.query.order_by(model.id.desc()).limit(20).all()
        for row in rows:
            jobs.append(
                {
                    "kind": kind,
                    "id": row.id,
                    "label": label(row),
                    "status": row.status,
                    "stage": getattr(row, "stage", None) or None,
                    "error": row.error,
                    "allotment_id": row.allotment_id,
                    "created_at": row.created_at,
                    "started_at": getattr(row, "started_at", None)
                    or getattr(row, "posted_at", None),
                    "finished_at": getattr(row, "finished_at", None),
                }
            )
        counts.append(
            {
                "kind": kind,
                "waiting": model.query.filter(model.status.in_(waiting)).count(),
                "failed_24h": model.query.filter(
                    model.status == failed, model.created_at >= day_ago
                ).count(),
            }
        )
    names = dict(
        db.session.query(Allotment.id, Allotment.name)
        .filter(Allotment.id.in_({j["allotment_id"] for j in jobs}))
        .all()
    )
    for job in jobs:
        job["allotment_name"] = names.get(job["allotment_id"])
    jobs.sort(key=lambda j: j["created_at"], reverse=True)
    return jobs[:40], counts


@blp.route("/jobs")
class Jobs(MethodView):
    @require_admin
    @blp.response(200, JobsSchema)
    def get(self):
        """Recent map jobs, packet scans and Mastodon posts, and how many are waiting or failed."""
        jobs, counts = _jobs()
        return {"jobs": jobs, "counts": counts}


@blp.route("/logs")
class Logs(MethodView):
    @require_admin
    @blp.arguments(LogQuerySchema, location="query")
    @blp.response(200, LogsSchema)
    def get(self, args):
        """Stored log lines, newest first: warnings, errors and task outcomes."""
        query = LogEntry.query
        if level := args.get("level"):
            query = query.filter(LogEntry.level.in_(LEVEL_ORDER[LEVEL_ORDER.index(level) :]))
        for field in ("service", "request_id", "task_id"):
            if value := args.get(field):
                query = query.filter(getattr(LogEntry, field) == value)
        if q := args.get("q"):
            query = query.filter(LogEntry.event.ilike(f"%{q}%"))
        if before := args.get("before_id"):
            query = query.filter(LogEntry.id < before)
        limit = args["limit"]
        rows = query.order_by(LogEntry.id.desc()).limit(limit + 1).all()
        more = len(rows) > limit
        rows = rows[:limit]
        services = [
            s for (s,) in db.session.query(LogEntry.service).distinct().order_by(LogEntry.service)
        ]
        return {
            "entries": rows,
            "next_before": rows[-1].id if more else None,
            "services": services,
        }
