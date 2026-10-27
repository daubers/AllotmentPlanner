import logging
import sys
import uuid

import structlog
from flask import Flask, g, request

REQUEST_ID_HEADER = "X-Request-ID"


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(stream=sys.stdout, format="%(message)s", level=level)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.format_exc_info,
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
            log.info("request", method=request.method, path=request.path, status=response.status_code)
        return response
