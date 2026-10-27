import time

from flask import Flask, Response, g, request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

HTTP_REQUESTS = Counter(
    "allotment_http_requests_total", "HTTP requests", ["method", "route", "status"]
)
HTTP_LATENCY = Histogram(
    "allotment_http_request_seconds", "HTTP request latency", ["method", "route"]
)
DOMAIN_EVENTS = Counter("allotment_domain_events_total", "Domain events emitted", ["type"])


def count_event(event) -> None:
    DOMAIN_EVENTS.labels(type=event.type).inc()


def init_metrics(app: Flask) -> None:
    @app.before_request
    def _start_timer() -> None:
        g._started = time.perf_counter()

    @app.after_request
    def _record(response):
        route = request.url_rule.rule if request.url_rule else "unmatched"
        HTTP_REQUESTS.labels(request.method, route, response.status_code).inc()
        if "_started" in g:
            HTTP_LATENCY.labels(request.method, route).observe(time.perf_counter() - g._started)
        return response

    @app.get("/metrics")
    def metrics() -> Response:
        return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
