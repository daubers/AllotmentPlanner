from datetime import UTC, date, datetime, timedelta

from allotment.api.overview import _streaks
from allotment.extensions import db
from allotment.models import ActivityLog


def d(n):
    return date(2026, 6, 10) + timedelta(days=n)


def test_streak_alive_when_last_active_day_was_yesterday():
    assert _streaks({d(-3), d(-2), d(-1)}, d(0)) == {"current": 3, "longest": 3}


def test_streak_broken_after_a_missed_day():
    assert _streaks({d(-4), d(-3)}, d(0)) == {"current": 0, "longest": 2}


def test_longest_streak_is_found_in_the_past():
    active = {d(-20), d(-19), d(-18), d(-17), d(-1), d(0)}
    assert _streaks(active, d(0)) == {"current": 2, "longest": 4}


def test_streak_of_nothing():
    assert _streaks(set(), d(0)) == {"current": 0, "longest": 0}


def _plot(client, register):
    headers, _ = register()
    pid = client.post("/api/v1/allotments", json={"name": "Plot"}, headers=headers).json["id"]
    return headers, f"/api/v1/allotments/{pid}", pid


def test_events_are_logged_and_counted(client, register):
    headers, base, _ = _plot(client, register)
    t = client.post(f"{base}/tasks", json={"title": "Sow peas"}, headers=headers).json
    client.post(f"{base}/tasks/{t['id']}/complete", headers=headers)
    data = client.get(f"{base}/overview", headers=headers).json
    today = data["days"][-1]
    assert today["date"] == datetime.now(UTC).date().isoformat()
    assert today["tasks_added"] == 1
    assert today["tasks_done"] == 1
    assert data["totals"]["tasks_done"] == 1
    assert data["streak"] == {"current": 1, "longest": 1}
    assert data["recent_done"][0]["title"] == "Sow peas"
    assert data["open_tasks"] == 0


def test_window_length_and_week_split(client, register, app):
    headers, base, pid = _plot(client, register)
    today = date(2026, 6, 10)  # a Wednesday; this week starts Mon 8th
    for when, kind in [
        (today - timedelta(days=1), "task.completed"),
        (today - timedelta(days=2), "task.completed"),
        (today - timedelta(days=4), "task.completed"),  # last week (Sat 6th)
        (today - timedelta(days=40), "media.uploaded"),
    ]:
        db.session.add(
            ActivityLog(
                allotment_id=pid,
                type=kind,
                occurred_at=datetime.combine(when, datetime.min.time(), UTC),
            )
        )
    db.session.commit()
    data = client.get(
        f"{base}/overview", query_string={"days": 30, "today": "2026-06-10"}, headers=headers
    ).json
    assert len(data["days"]) == 30
    assert data["days"][-1]["date"] == "2026-06-10"
    assert data["this_week"]["tasks_done"] == 2  # Mon 8th and Tue 9th
    assert data["last_week"]["tasks_done"] == 1
    assert data["totals"]["photos_added"] == 1  # outside the 30-day window but in totals
    assert data["totals"]["active_days"] == 4
    assert data["streak"] == {"current": 2, "longest": 2}  # 8th-9th; today not over yet


def test_bulk_replace_counts_each_feature(client, register):
    headers, base, _ = _plot(client, register)
    bed = {
        "type": "Polygon",
        "coordinates": [[[-1, 51], [-1, 51.001], [-0.999, 51.001], [-0.999, 51], [-1, 51]]],
    }
    body = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "geometry": bed, "properties": {"name": n, "kind": "bed"}}
            for n in ("A", "B", "C")
        ],
    }
    assert client.put(f"{base}/features", json=body, headers=headers).status_code == 200
    assert client.get(f"{base}/overview", headers=headers).json["totals"]["map_edits"] == 3


def test_overview_is_per_allotment_and_needs_membership(client, register):
    owner, _ = register("o@example.com", "O")
    other, _ = register("x@example.com", "X")
    pid = client.post("/api/v1/allotments", json={"name": "P"}, headers=owner).json["id"]
    client.post(f"/api/v1/allotments/{pid}/tasks", json={"title": "t"}, headers=owner)
    pid2 = client.post("/api/v1/allotments", json={"name": "Q"}, headers=other).json["id"]
    assert client.get(f"/api/v1/allotments/{pid}/overview", headers=other).status_code == 404
    assert (
        client.get(f"/api/v1/allotments/{pid2}/overview", headers=other).json["totals"][
            "tasks_added"
        ]
        == 0
    )
    assert client.get(f"/api/v1/allotments/{pid}/overview").status_code == 401
