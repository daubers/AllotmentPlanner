import structlog
from celery import Celery, signals

from .config import Config
from .logging import configure_logging

celery = Celery("allotment", broker=Config.REDIS_URL, backend=Config.REDIS_URL)
celery.conf.update(
    task_track_started=True,
    worker_send_task_events=True,
    task_send_sent_event=True,
    task_default_headers={},
)


@signals.before_task_publish.connect
def _propagate_request_id(headers=None, **_):
    """Carry the API request ID into the task so one action can be traced end to end."""
    request_id = structlog.contextvars.get_contextvars().get("request_id")
    if request_id and headers is not None:
        headers["request_id"] = request_id


@signals.task_prerun.connect
def _bind_task_context(task_id=None, task=None, **_):
    structlog.contextvars.clear_contextvars()
    request_id = getattr(task.request, "request_id", None)
    structlog.contextvars.bind_contextvars(task_id=task_id, request_id=request_id)


@signals.setup_logging.connect
def _setup_logging(**_):
    configure_logging(Config.LOG_LEVEL)


@celery.task(name="allotment.ping")
def ping() -> str:
    structlog.get_logger("tasks").info("ping")
    return "pong"
