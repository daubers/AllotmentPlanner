import logging
import sys
import uuid

import structlog
from flask import Flask, g, request

from . import ops_log

REQUEST_ID_HEADER = "X-Request-ID"


_sink: ops_log.Sink | None = None
_handler: logging.Handler | None = None


def configure_logging(level: str = "INFO", store_url: str | None = None) -> None:
    """Log JSON to stdout; with ``store_url`` also keep the lines the admin page shows."""
    global _sink, _handler
    logging.basicConfig(stream=sys.stdout, format="%(message)s", level=level)
    root = logging.getLogger()
    if _handler is not None:
        root.removeHandler(_handler)
        _handler = None
    if _sink is not None:
        _sink.dispose()
        _sink = None
    stored = []
    if store_url:
        _sink = ops_log.Sink(store_url)
        _handler = ops_log.StdlibHandler(_sink)
        root.addHandler(_handler)
        stored = [ops_log.structlog_processor(_sink)]
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.format_exc_info,
            *stored,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
        cache_logger_on_first_use=True,
    )


def init_request_logging(app: Flask) -> None:
    log = structlog.get_logger("request")

    @app.before_request
    def _bind_request_id() -> None:
        g.request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=g.request_id)

    @app.after_request
    def _log_response(response):
        response.headers[REQUEST_ID_HEADER] = g.get("request_id", "")
        if request.path not in ("/healthz", "/readyz", "/metrics"):
            (log.error if response.status_code >= 500 else log.info)(
                "request", method=request.method, path=request.path, status=response.status_code
            )
        return response
