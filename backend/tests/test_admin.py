from datetime import UTC, datetime, timedelta

import pytest
import structlog

from allotment import celery_app
from allotment.api import admin
from allotment.celery_app import ping
from allotment.config import TestConfig
from allotment.extensions import db
from allotment.logging import configure_logging
from allotment.models import LogEntry, MapJob, MastodonPost, PacketScan, User
from allotment.tasks import prune_logs

URLS = ["/workers", "/system", "/jobs", "/logs"]


@pytest.fixture
def admin_headers(register, app):
    headers, user = register("boss@example.com", "Boss")
    db.session.get(User, user["id"]).is_admin = True
    db.session.commit()
    return headers


@pytest.fixture
def no_broker(monkeypatch):
    """The workers page without a real Celery broker."""
    monkeypatch.setattr(admin, "_inspect", lambda: {})
    monkeypatch.setattr(admin, "_queue_depths", lambda: {"celery": 2, "mapping": 0, "vision": 5})


def add_log(level="info", event="hello", service="api", **fields):
    entry = LogEntry(level=level, event=event, service=service, host="h", **fields)
    db.session.add(entry)
    db.session.commit()
    return entry


@pytest.mark.parametrize("url", URLS)
def test_admin_endpoints_need_an_admin(client, register, url):
    assert client.get(f"/api/v1/admin{url}").status_code == 401
    headers, _ = register()
    assert client.get(f"/api/v1/admin{url}", headers=headers).status_code == 403


def test_me_says_whether_you_are_an_admin(client, register, admin_headers):
    assert client.get("/api/v1/auth/me", headers=admin_headers).json["is_admin"] is True
    headers, _ = register("plain@example.com")
    assert client.get("/api/v1/auth/me", headers=headers).json["is_admin"] is False


def test_make_admin_command(app, register):
    _, user = register("someone@example.com")
    runner = app.test_cli_runner()
    result = runner.invoke(args=["make-admin", "SOMEONE@example.com"])
    assert "now an admin" in result.output
    assert db.session.get(User, user["id"]).is_admin is True
    runner.invoke(args=["make-admin", "someone@example.com", "--revoke"])
    db.session.expire_all()
    assert db.session.get(User, user["id"]).is_admin is False
    assert runner.invoke(args=["make-admin", "nobody@example.com"]).exit_code != 0


def test_collect_workers_joins_what_each_worker_said():
    now = 1000.0
    workers = admin.collect_workers(
        stats={
            "celery@a": {
                "pid": 7,
                "uptime": 90,
                "pool": {"max-concurrency": 2},
                "total": {"x": 3, "y": 4},
            }
        },
        active={"celery@a": [{"id": "t1", "name": "allotment.run_map_job", "time_start": 940.0}]},
        reserved={"celery@a": [{}, {}]},
        queues={"celery@a": [{"name": "mapping"}, {"name": "vision"}]},
        info={"celery@a": {"version": "0.8.1", "gpu": "RX 6600"}},
        now=now,
    )
    assert workers == [
        {
            "name": "celery@a",
            "queues": ["mapping", "vision"],
            "concurrency": 2,
            "pid": 7,
            "uptime_seconds": 90,
            "processed": 7,
            "reserved": 2,
            "active": [{"id": "t1", "name": "allotment.run_map_job", "running_seconds": 60.0}],
            "version": "0.8.1",
            "gpu": "RX 6600",
        }
    ]


def test_collect_workers_with_nobody_answering():
    assert admin.collect_workers(None, None, None, None, None) == []


def test_workers_endpoint_lists_queues_and_consumers(client, admin_headers, monkeypatch):
    answers = {
        "stats": {"celery@gpu": {"pid": 1, "uptime": 5, "pool": {"max-concurrency": 1}}},
        "active": {"celery@gpu": []},
        "reserved": {"celery@gpu": []},
        "queues": {"celery@gpu": [{"name": "vision"}]},
        "info": {"celery@gpu": {"version": "0.8.1", "gpu": None}},
    }
    monkeypatch.setattr(admin, "_inspect", lambda: answers)
    monkeypatch.setattr(admin, "_queue_depths", lambda: {"celery": 0, "mapping": 3, "vision": 1})
    body = client.get("/api/v1/admin/workers", headers=admin_headers).json
    assert [w["name"] for w in body["workers"]] == ["celery@gpu"]
    queues = {q["name"]: q for q in body["queues"]}
    assert queues["vision"] == {"name": "vision", "depth": 1, "consumers": 1}
    assert queues["mapping"] == {"name": "mapping", "depth": 3, "consumers": 0}
    assert body["error"] is None


def test_workers_endpoint_reports_an_unreachable_broker(client, admin_headers, monkeypatch):
    def boom():
        raise ConnectionError("no redis")

    monkeypatch.setattr(admin, "_inspect", boom)
    monkeypatch.setattr(
        admin, "_queue_depths", lambda: {"celery": None, "mapping": None, "vision": None}
    )
    body = client.get("/api/v1/admin/workers", headers=admin_headers).json
    assert body["workers"] == []
    assert "ConnectionError" in body["error"]


def test_workers_endpoint_shows_the_schedule_and_last_run(client, admin_headers, no_broker):
    add_log(event="task.finished", data={"task": "allotment.mastodon_sweep", "state": "SUCCESS"})
    beat = {
        b["name"]: b
        for b in client.get("/api/v1/admin/workers", headers=admin_headers).json["beat"]
    }
    assert beat["mastodon-sweep"]["schedule"] == "every 5 min"
    assert beat["mastodon-sweep"]["last_state"] == "SUCCESS"
    assert beat["mastodon-sweep"]["last_run"]
    assert beat["mastodon-daily-digest"]["schedule"].startswith("daily at ")
    assert beat["mastodon-daily-digest"]["last_run"] is None


def test_system_endpoint(client, admin_headers, app):
    body = client.get("/api/v1/admin/system", headers=admin_headers).json
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["storage"] == "ok"
    assert body["version"] == app.config["APP_VERSION"]
    assert body["users"] == 1
    assert body["log_retention_days"] == 14


def test_logs_are_newest_first_and_filterable(client, admin_headers):
    add_log("info", "started", service="worker")
    add_log("warning", "slow thing", service="api", request_id="r1")
    add_log("error", "Boom happened", service="worker", task_id="t9")
    url = "/api/v1/admin/logs"

    def fetch(**params):
        return [
            e["event"]
            for e in client.get(url, headers=admin_headers, query_string=params).json["entries"]
        ]

    assert fetch() == ["Boom happened", "slow thing", "started"]
    assert fetch(level="warning") == ["Boom happened", "slow thing"]
    assert fetch(level="error") == ["Boom happened"]
    assert fetch(service="worker") == ["Boom happened", "started"]
    assert fetch(q="boom") == ["Boom happened"]
    assert fetch(request_id="r1") == ["slow thing"]
    assert fetch(task_id="t9") == ["Boom happened"]
    assert client.get(url, headers=admin_headers).json["services"] == ["api", "worker"]
    assert client.get(url, headers=admin_headers, query_string={"level": "loud"}).status_code == 422


def test_logs_page_through_with_before_id(client, admin_headers):
    for i in range(5):
        add_log(event=f"line {i}")
    url = "/api/v1/admin/logs"
    first = client.get(url, headers=admin_headers, query_string={"limit": 2}).json
    assert [e["event"] for e in first["entries"]] == ["line 4", "line 3"]
    second = client.get(
        url, headers=admin_headers, query_string={"limit": 2, "before_id": first["next_before"]}
    ).json
    assert [e["event"] for e in second["entries"]] == ["line 2", "line 1"]
    last = client.get(
        url, headers=admin_headers, query_string={"limit": 2, "before_id": second["next_before"]}
    ).json
    assert [e["event"] for e in last["entries"]] == ["line 0"]
    assert last["next_before"] is None


def test_jobs_lists_recent_work_and_counts(client, admin_headers, register):
    headers, _ = register("owner@example.com", "Owner")
    allotment_id = client.post("/api/v1/allotments", json={"name": "Plot"}, headers=headers).json[
        "id"
    ]
    db.session.add_all(
        [
            MapJob(
                allotment_id=allotment_id, name="Whole plot", status="running", stage="matching"
            ),
            MapJob(allotment_id=allotment_id, name="Old", status="failed", error="out of memory"),
            PacketScan(allotment_id=allotment_id, status="queued"),
            MastodonPost(
                allotment_id=allotment_id,
                kind="digest",
                text="x",
                status="failed",
                error="401",
                idempotency_key="k",
            ),
        ]
    )
    db.session.commit()
    body = client.get("/api/v1/admin/jobs", headers=admin_headers).json
    assert {j["kind"] for j in body["jobs"]} == {"map", "scan", "mastodon"}
    running = next(j for j in body["jobs"] if j["label"] == "Whole plot")
    assert running["allotment_name"] == "Plot"
    assert running["stage"] == "matching"
    counts = {c["kind"]: c for c in body["counts"]}
    assert counts["map"] == {"kind": "map", "waiting": 1, "failed_24h": 1}
    assert counts["scan"]["waiting"] == 1
    assert counts["mastodon"]["failed_24h"] == 1


@pytest.fixture
def stored_logs(app):
    """Logging that keeps its lines in the database, as in production."""
    configure_logging("INFO", app.config["SQLALCHEMY_DATABASE_URI"])
    # structlog pins a logger's setup the first time it is used. Whichever earlier test ran a task
    # first pinned this one without the database sink, so make a fresh one.
    celery_app._task_log = structlog.get_logger("tasks")
    yield
    configure_logging("INFO")
    celery_app._task_log = structlog.get_logger("tasks")


def stored():
    db.session.expire_all()
    return LogEntry.query.order_by(LogEntry.id).all()


def test_warnings_and_task_outcomes_are_kept_but_ordinary_lines_are_not(stored_logs):
    log = structlog.get_logger("test")
    log.info("just chatter")
    log.warning("careful", thing=3)
    log.info("job done", persist=True, ok=True)
    try:
        raise ValueError("bad")
    except ValueError:
        log.exception("it broke")
    rows = stored()
    assert [r.event.split("\n")[0] for r in rows] == ["careful", "job done", "it broke"]
    assert rows[0].level == "warning"
    assert rows[0].data == {"thing": 3}
    assert rows[1].level == "info"
    assert "ValueError: bad" in rows[2].event
    assert rows[0].service == "api"


def test_standard_library_errors_are_kept(stored_logs):
    import logging

    logging.getLogger("celery.app.trace").error("Task blew up")
    logging.getLogger("sqlalchemy.engine").error("not recursion please")
    assert [r.event for r in stored()] == ["Task blew up"]


def test_request_ids_are_kept_with_the_line(stored_logs):
    structlog.contextvars.bind_contextvars(request_id="abc", task_id="t1")
    try:
        structlog.get_logger("test").warning("tagged")
    finally:
        structlog.contextvars.clear_contextvars()
    row = stored()[0]
    assert (row.request_id, row.task_id) == ("abc", "t1")


def test_a_broken_log_store_never_breaks_the_caller(media_root):
    class Config(TestConfig):
        MEDIA_ROOT = str(media_root)
        LOG_TO_DB = True
        SQLALCHEMY_DATABASE_URI = "postgresql+psycopg://nobody:nope@127.0.0.1:1/none"

    configure_logging("INFO", Config.SQLALCHEMY_DATABASE_URI)
    try:
        structlog.get_logger("test").error("still fine")
    finally:
        configure_logging("INFO")


def test_a_finished_task_leaves_an_entry(stored_logs):
    assert ping.delay().get() == "pong"
    done = [r for r in stored() if r.event == "task.finished"]
    assert done[-1].data["task"] == "allotment.ping"
    assert done[-1].data["state"] == "SUCCESS"
    assert done[-1].level == "info"


def test_prune_logs_drops_only_old_lines(app):
    old = datetime.now(UTC) - timedelta(days=30)
    add_log(event="ancient", at=old)
    add_log(event="recent")
    assert prune_logs() == 1
    assert [r.event for r in LogEntry.query.all()] == ["recent"]
