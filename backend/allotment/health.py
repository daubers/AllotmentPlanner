import redis
from flask import Blueprint, current_app, jsonify
from sqlalchemy import text

from .extensions import db

bp = Blueprint("health", __name__)


@bp.get("/healthz")
def healthz():
    """Liveness: the process is up."""
    return jsonify(status="ok")


@bp.get("/readyz")
def readyz():
    """Readiness: dependencies are reachable."""
    checks = {}
    try:
        db.session.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as exc:
        checks["db"] = f"error: {exc.__class__.__name__}"
    if not current_app.testing:
        try:
            redis.Redis.from_url(current_app.config["REDIS_URL"], socket_timeout=2).ping()
            checks["redis"] = "ok"
        except Exception as exc:
            checks["redis"] = f"error: {exc.__class__.__name__}"
    ready = all(v == "ok" for v in checks.values())
    return jsonify(status="ok" if ready else "unavailable", checks=checks), 200 if ready else 503
