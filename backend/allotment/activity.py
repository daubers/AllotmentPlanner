"""Event-bus subscriber that persists domain events as ``ActivityLog`` rows."""

import structlog

from .events import Event
from .extensions import db
from .models import ActivityLog

log = structlog.get_logger(__name__)

# Events that make up the progress story. Everything else (logins, membership churn) is skipped.
RECORDED = {
    "task.created",
    "task.completed",
    "task.reopened",
    "media.uploaded",
    "feature.created",
    "feature.updated",
    "feature.deleted",
    "feature.bulk_replaced",
    "layer.created",
    "packet.created",
    "measurements.applied",
}


def record_activity(event: Event) -> None:
    if event.type not in RECORDED or event.allotment_id is None:
        return
    db.session.add(
        ActivityLog(
            allotment_id=event.allotment_id,
            actor_id=event.actor_id,
            type=event.type,
            subject=event.subject,
            payload=event.payload,
            occurred_at=event.occurred_at,
        )
    )
    db.session.commit()
