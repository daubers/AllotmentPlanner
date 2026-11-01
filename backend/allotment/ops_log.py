"""Keeps the log lines worth looking back at in the database, for the admin page.

Everything is still written to stdout as before. On top of that, warnings and errors (from structlog
and from the standard library, which is where Celery and Flask report crashes) and the events marked
``persist=True`` (task outcomes) are stored in ``log_entries``. Writing a log line must never break
the code that logged it, so every failure here is swallowed.
"""

import json
import logging
import socket
from datetime import UTC, datetime

from sqlalchemy import create_engine, insert

from .models import LogEntry

_LEVELS = {"debug": 10, "info": 20, "warning": 30, "warn": 30, "error": 40, "critical": 50}
_SKIP_LOGGERS = ("sqlalchemy", "alembic", "allotment.ops_log")
_RESERVED = {"event", "level", "timestamp", "request_id", "task_id", "persist", "exception"}

_service = ""
_host = socket.gethostname()


def set_service(name: str) -> None:
    """Name this process (api, worker, beat). The first caller wins: a worker builds an app too."""
    global _service
    if not _service:
        _service = name


class Sink:
    """Writes entries to the database over its own connection, apart from the app's session."""

    def __init__(self, url: str, keep_level: str = "warning"):
        self.engine = create_engine(url, pool_size=1, max_overflow=1, pool_pre_ping=True)
        self.keep = _LEVELS.get(keep_level.lower(), 30)

    def keeps(self, level: str, persist: bool = False) -> bool:
        return persist or _LEVELS.get(level.lower(), 20) >= self.keep

    def write(self, level: str, event: str, request_id=None, task_id=None, data=None) -> None:
        try:
            clean = json.loads(json.dumps(data, default=str)) if data else None
            row = {
                "at": datetime.now(UTC),
                "service": _service or "api",
                "host": _host,
                "level": "warning" if level.lower() == "warn" else level.lower(),
                "event": str(event)[:20000],
                "request_id": request_id,
                "task_id": task_id,
                "data": clean,
            }
            with self.engine.begin() as conn:
                conn.execute(insert(LogEntry.__table__).values(**row))
        except Exception:  # noqa: BLE001 - logging must not take the caller down
            pass

    def dispose(self) -> None:
        self.engine.dispose()


def structlog_processor(sink: Sink):
    def process(_logger, method_name, event_dict):
        level = str(event_dict.get("level") or method_name)
        if sink.keeps(level, bool(event_dict.get("persist"))):
            event = event_dict.get("event", "")
            if event_dict.get("exception"):
                event = f"{event}\n{event_dict['exception']}"
            sink.write(
                level,
                event,
                request_id=event_dict.get("request_id"),
                task_id=event_dict.get("task_id"),
                data={k: v for k, v in event_dict.items() if k not in _RESERVED},
            )
        return event_dict

    return process


class StdlibHandler(logging.Handler):
    """Stores warnings and errors raised through the standard logging module."""

    def __init__(self, sink: Sink):
        super().__init__(level=logging.WARNING)
        self.sink = sink

    def emit(self, record: logging.LogRecord) -> None:
        if record.name.startswith(_SKIP_LOGGERS):
            return
        try:
            message = self.format(record)
        except Exception:  # noqa: BLE001
            message = str(record.msg)
        self.sink.write(record.levelname, message, data={"logger": record.name})
