from allotment import events


def test_healthz(client):
    assert client.get("/healthz").json == {"status": "ok"}


def test_readyz_checks_db(client):
    resp = client.get("/readyz")
    assert resp.status_code == 200
    assert resp.json["checks"]["db"] == "ok"


def test_request_id_is_generated_and_echoed(client):
    assert client.get("/healthz").headers["X-Request-ID"]
    assert client.get("/healthz", headers={"X-Request-ID": "abc"}).headers["X-Request-ID"] == "abc"


def test_metrics_endpoint_counts_requests(client):
    client.get("/healthz")
    body = client.get("/metrics").get_data(as_text=True)
    assert 'allotment_http_requests_total{method="GET",route="/healthz",status="200"}' in body


def test_emit_reaches_subscribers_and_metrics(client):
    seen = []
    events.subscribe("task.completed", seen.append)
    events.emit("task.completed", actor_id=1, subject={"task_id": 5})
    assert seen[0].subject == {"task_id": 5}
    assert 'allotment_domain_events_total{type="task.completed"}' in client.get(
        "/metrics"
    ).get_data(as_text=True)


def test_failing_subscriber_does_not_break_emit(client):
    def boom(_event):
        raise RuntimeError("nope")

    events.subscribe("x", boom)
    assert events.emit("x").type == "x"
