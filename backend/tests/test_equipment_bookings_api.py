from datetime import date, timedelta

from allotment import events

from .test_equipment_api import add as add_equipment
from .test_media import plot  # noqa: F401 - owner, editor, viewer, stranger and a bed ("Bed 1")
from .test_plantings_api import INSIDE, packet, sow

TODAY = date.today()


def day(n):
    return (TODAY + timedelta(days=n)).isoformat()


def cloches(client, plot, quantity=6, **kw):  # noqa: F811
    return add_equipment(
        client, plot, name="Glass cloches", kind="cloche", quantity=quantity, **kw
    ).json["id"]


def book(client, plot, equipment_id, who="editor", **kw):  # noqa: F811
    body = {"feature_id": plot["bed"], "starts_on": day(0), "ends_on": day(30), "quantity": 1, **kw}
    return client.post(
        f"{plot['base']}/equipment/{equipment_id}/bookings", json=body, headers=plot[who]
    )


def test_put_equipment_to_use_on_a_bed(client, plot):  # noqa: F811
    a = cloches(client, plot)
    resp = book(client, plot, a, quantity=4, note="over the lettuce")
    assert resp.status_code == 201, resp.json
    b = resp.json
    assert (b["equipment_name"], b["equipment_quantity"], b["quantity"], b["note"]) == (
        "Glass cloches",
        6,
        4,
        "over the lettuce",
    )
    assert (b["feature_id"], b["feature_name"], b["planting_id"], b["warnings"]) == (
        plot["bed"],
        "Bed 1",
        None,
        [],
    )
    assert (b["starts_on"], b["ends_on"]) == (day(0), day(30))


def test_or_on_a_planting(client, plot):  # noqa: F811
    a = cloches(client, plot)
    pid = packet(client, plot, name="Lettuce")
    planting = sow(client, plot, INSIDE, packet_id=pid).json
    resp = client.post(
        f"{plot['base']}/equipment/{a}/bookings",
        json={"planting_id": planting["id"], "starts_on": day(0), "ends_on": day(14)},
        headers=plot["editor"],
    )
    assert resp.status_code == 201, resp.json
    assert (resp.json["planting_label"], resp.json["feature_id"]) == ("Lettuce in Bed 1", None)


def test_it_needs_exactly_one_target(client, plot):  # noqa: F811
    a = cloches(client, plot)
    url = f"{plot['base']}/equipment/{a}/bookings"
    both = {"feature_id": plot["bed"], "planting_id": 1, "starts_on": day(0), "ends_on": day(5)}
    neither = {"starts_on": day(0), "ends_on": day(5)}
    for body in (both, neither):
        assert client.post(url, json=body, headers=plot["editor"]).status_code == 422


def test_dates_must_run_forwards(client, plot):  # noqa: F811
    a = cloches(client, plot)
    assert book(client, plot, a, starts_on=day(5), ends_on=day(5)).status_code == 422
    assert book(client, plot, a, starts_on=day(5), ends_on=day(1)).status_code == 422
    assert book(client, plot, a, quantity=0).status_code == 422


def test_booking_more_than_you_own_is_allowed_with_a_warning(client, plot):  # noqa: F811
    a = cloches(client, plot, quantity=6)
    first = book(client, plot, a, quantity=5, starts_on=day(0), ends_on=day(30)).json
    assert first["warnings"] == []
    second = book(client, plot, a, quantity=3, starts_on=day(10), ends_on=day(40))
    assert second.status_code == 201
    (w,) = second.json["warnings"]
    assert (w["from"], w["to"], w["used"], w["over"]) == (day(10), day(30), 8, 2)
    assert w["booking_ids"] == sorted([first["id"], second.json["id"]])
    # the first booking, looked at again, shows it is part of the same clash
    listed = client.get(f"{plot['base']}/equipment/{a}/bookings", headers=plot["viewer"]).json
    assert listed["quantity"] == 6 and len(listed["bookings"]) == 2
    assert [(c["used"], c["over"]) for c in listed["conflicts"]] == [(8, 2)]


def test_back_to_back_bookings_are_fine(client, plot):  # noqa: F811
    a = cloches(client, plot, quantity=6)
    book(client, plot, a, quantity=6, starts_on=day(0), ends_on=day(10))
    resp = book(client, plot, a, quantity=6, starts_on=day(10), ends_on=day(20))
    assert resp.json["warnings"] == []


def test_edit_and_remove(client, plot):  # noqa: F811
    a = cloches(client, plot)
    b = book(client, plot, a, quantity=2).json
    url = f"{plot['base']}/equipment-bookings/{b['id']}"
    resp = client.patch(
        url, json={"quantity": 6, "ends_on": day(45), "note": "longer"}, headers=plot["editor"]
    )
    assert resp.status_code == 200, resp.json
    assert (resp.json["quantity"], resp.json["ends_on"], resp.json["note"]) == (
        6,
        day(45),
        "longer",
    )
    assert client.patch(url, json={"ends_on": day(-1)}, headers=plot["editor"]).status_code == 422
    assert client.get(f"{plot['base']}/equipment/{a}/bookings", headers=plot["viewer"]).json[
        "bookings"
    ][0]["ends_on"] == day(45)
    assert client.delete(url, headers=plot["editor"]).status_code == 204
    assert client.delete(url, headers=plot["editor"]).status_code == 404


def test_the_list_can_be_filtered(client, plot):  # noqa: F811
    a, b = (
        cloches(client, plot),
        add_equipment(client, plot, name="Fleece", kind="fleece").json["id"],
    )
    book(client, plot, a, starts_on=day(0), ends_on=day(10))
    book(client, plot, b, starts_on=day(50), ends_on=day(60))
    base = f"{plot['base']}/equipment-bookings"

    def names(q=""):
        rows = client.get(base + q, headers=plot["viewer"]).json
        return [x["equipment_name"] for x in rows]

    assert names() == ["Glass cloches", "Fleece"]  # soonest first
    assert names(f"?equipment_id={b}") == ["Fleece"]
    assert names(f"?feature_id={plot['bed']}") == ["Glass cloches", "Fleece"]
    assert names("?feature_id=999999") == []
    assert names(f"?from={day(20)}&to={day(55)}") == ["Fleece"]  # the first ended before the window
    assert names(f"?from={day(10)}") == ["Fleece"]  # it is free again on its end day


def test_it_cannot_reach_other_allotments(client, plot, register):  # noqa: F811
    a = cloches(client, plot)
    other, _ = register("other@example.com", "Other")
    oid = client.post("/api/v1/allotments", json={"name": "Elsewhere"}, headers=other).json["id"]
    bed = client.post(
        f"/api/v1/allotments/{oid}/features",
        json={
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [0, 0]},
            "properties": {"kind": "bed"},
        },
        headers=other,
    ).json["id"]
    assert book(client, plot, a, feature_id=bed).status_code == 422
    assert book(client, plot, a, feature_id=999999).status_code == 422
    mine = book(client, plot, a).json
    assert (
        client.get(f"/api/v1/allotments/{oid}/equipment/{a}/bookings", headers=other).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/v1/allotments/{oid}/equipment-bookings/{mine['id']}",
            json={"note": "x"},
            headers=other,
        ).status_code
        == 404
    )
    assert client.get(f"/api/v1/allotments/{oid}/equipment-bookings", headers=other).json == []


def test_roles(client, plot):  # noqa: F811
    a = cloches(client, plot)
    assert book(client, plot, a, who="viewer").status_code == 403
    assert book(client, plot, a, who="stranger").status_code == 404
    b = book(client, plot, a).json
    url = f"{plot['base']}/equipment-bookings/{b['id']}"
    assert (
        client.get(f"{plot['base']}/equipment-bookings", headers=plot["viewer"]).status_code == 200
    )
    assert client.patch(url, json={"note": "x"}, headers=plot["viewer"]).status_code == 403
    assert client.delete(url, headers=plot["viewer"]).status_code == 403


def test_bookings_go_with_what_they_belong_to(client, plot):  # noqa: F811
    a = cloches(client, plot)
    book(client, plot, a)
    client.delete(f"{plot['base']}/features/{plot['bed']}", headers=plot["owner"])
    assert (
        client.get(f"{plot['base']}/equipment/{a}/bookings", headers=plot["viewer"]).json[
            "bookings"
        ]
        == []
    )
    book_again = cloches(client, plot)
    other_bed = client.post(
        f"{plot['base']}/features",
        json={
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-1, 51]},
            "properties": {"kind": "bed", "name": "Pot"},
        },
        headers=plot["owner"],
    ).json["id"]
    book(client, plot, book_again, feature_id=other_bed)
    client.delete(f"{plot['base']}/equipment/{book_again}", headers=plot["editor"])
    assert client.get(f"{plot['base']}/equipment-bookings", headers=plot["viewer"]).json == []


def test_lowering_the_quantity_owned_makes_a_warning_not_an_error(client, plot):  # noqa: F811
    a = cloches(client, plot, quantity=6)
    book(client, plot, a, quantity=6)
    resp = client.patch(
        f"{plot['base']}/equipment/{a}", json={"quantity": 2}, headers=plot["editor"]
    )
    assert resp.status_code == 200
    got = client.get(f"{plot['base']}/equipment/{a}/bookings", headers=plot["viewer"]).json
    assert [(c["used"], c["over"]) for c in got["conflicts"]] == [(6, 4)]


def test_events_are_emitted(client, plot):  # noqa: F811
    seen = []
    events.subscribe(events.WILDCARD, lambda e: seen.append(e.type))
    a = cloches(client, plot)
    b = book(client, plot, a).json
    client.patch(
        f"{plot['base']}/equipment-bookings/{b['id']}", json={"note": "x"}, headers=plot["editor"]
    )
    client.delete(f"{plot['base']}/equipment-bookings/{b['id']}", headers=plot["editor"])
    assert [t for t in seen if t.startswith("equipment_booking.")] == [
        "equipment_booking.created",
        "equipment_booking.updated",
        "equipment_booking.deleted",
    ]
