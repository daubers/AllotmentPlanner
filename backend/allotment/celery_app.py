import os
import time

import structlog
from celery import Celery, signals
from celery.schedules import crontab
from celery.worker.control import inspect_command

from . import ops_log
from .config import Config
from .logging import configure_logging

celery = Celery(
    "allotment", broker=Config.REDIS_URL, backend=Config.REDIS_URL, include=["allotment.tasks"]
)
celery.conf.update(
    task_track_started=True,
    worker_send_task_events=True,
    task_send_sent_event=True,
    task_default_headers={},
    # Photogrammetry is heavy and slow, so it has its own queue and worker (the `mapper` service);
    # the default worker keeps handling thumbnails and Mastodon posts in the meantime.
    task_routes={
        "allotment.run_map_job": {"queue": "mapping"},
        # Reading a packet photo (OCR) is a minute of CPU, so it must not wait behind a map job.
        "allotment.run_packet_scan": {"queue": "vision"},
    },
    beat_schedule={
        "mastodon-daily-digest": {
            "task": "allotment.mastodon_daily_digest",
            "schedule": crontab(hour=Config.MASTODON_DIGEST_HOUR_UTC, minute=0),
        },
        "mastodon-sweep": {"task": "allotment.mastodon_sweep", "schedule": 300.0},
        "prune-logs": {"task": "allotment.prune_logs", "schedule": crontab(hour=3, minute=30)},
    },
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
    ops_log.set_service(os.environ.get("SERVICE_NAME", "worker"))
    store = Config.SQLALCHEMY_DATABASE_URI if Config.LOG_TO_DB else None
    configure_logging(Config.LOG_LEVEL, store)


_started: dict[str, float] = {}
_task_log = structlog.get_logger("tasks")


@signals.task_prerun.connect
def _note_start(task_id=None, **_):
    _started[task_id] = time.monotonic()


@signals.task_postrun.connect
def _log_outcome(task_id=None, task=None, state=None, **_):
    """One line per task run, kept for the admin page: what ran, how it ended, how long it took."""
    began = _started.pop(task_id, None)
    seconds = round(time.monotonic() - began, 2) if began is not None else None
    ok = state == "SUCCESS"
    (_task_log.info if ok else _task_log.warning)(
        "task.finished", persist=True, task=task.name, state=state, seconds=seconds
    )


@celery.task(name="allotment.ping")
def ping() -> str:
    structlog.get_logger("tasks").info("ping")
    return "pong"


_gpu_name: list = []


def _detect_gpu() -> str | None:
    """The GPU PyTorch can use here (CUDA or ROCm), or None. Only the mapper image has PyTorch."""
    if not _gpu_name:
        try:
            import torch

            _gpu_name.append(torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)
        except Exception:  # noqa: BLE001 - no PyTorch or no GPU
            _gpu_name.append(None)
    return _gpu_name[0]


@inspect_command()
def allotment_info(state):
    """Extra facts for the admin page, asked of each worker: the app version and its GPU."""
    return {"version": Config.APP_VERSION, "gpu": _detect_gpu()}
