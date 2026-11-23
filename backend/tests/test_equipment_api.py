import pytest

from allotment import events

from .test_media import plot  # noqa: F401 - owner, editor, viewer, stranger and a bed ("Bed 1")


def add(client, plot, who="editor", **kw):  # noqa: F811
    body = {"name": "Spade", "kind": "spade", **kw}
    return client.post(f"{plot['base']}/equipment", json=body, headers=plot[who])


def test_add_equipment(client, plot):  # noqa: F811
    resp = add(client, plot, quantity=2, notes="Ash handle", used_for="Dig, double digging")
    assert resp.status_code == 201, resp.json
    item = resp.json
    assert (item["name"], item["kind"], item["kind_label"], item["quantity"]) == (
        "Spade",
        "spade",
        "Spade",
        2,
    )
    assert (
        item["keywords"] == ["dig", "double digging"] and item["used_for"] == "Dig, double digging"
    )
    assert (item["status"], item["last_serviced_on"], item["location_name"]) == (
        "in_service",
        None,
        None,
    )
    got = client.get(f"{plot['base']}/equipment/{item['id']}", headers=plot["viewer"])
    assert got.status_code == 200 and got.json["notes"] == "Ash handle"


def test_defaults_and_other_kind(client, plot):  # noqa: F811
    item = client.post(
        f"{plot['base']}/equipment", json={"name": "Odd thing"}, headers=plot["editor"]
    ).json
    assert (item["kind"], item["kind_label"], item["quantity"], item["notes"]) == (
        None,
        "Other",
        1,
        "",
    )


def test_validation(client, plot):  # noqa: F811
    for bad in (
        {"name": ""},
        {"name": "x", "kind": "hammer"},
        {"name": "x", "quantity": 0},
        {"name": "x", "status": "lost"},
        {"name": "x", "used_for": "w" * 1001},
        {"quantity": 2},
    ):
        resp = client.post(f"{plot['base']}/equipment", json=bad, headers=plot["editor"])
        assert resp.status_code == 422, bad


def test_the_list_is_by_name_and_can_be_filtered(client, plot):  # noqa: F811
    add(client, plot, name="spade", kind="spade", notes="for digging")
    add(client, plot, name="Dibber", kind="dibber", used_for="sowing, seeds")
    add(client, plot, name="Old fork", kind="fork", status="out_of_action")
    names = lambda q="": [  # noqa: E731
        i["name"] for i in client.get(f"{plot['base']}/equipment{q}", headers=plot["viewer"]).json
    ]
    assert names() == ["Dibber", "Old fork", "spade"]  # case blind
    assert names("?kind=dibber") == ["Dibber"]
    assert names("?status=out_of_action") == ["Old fork"]
    assert names("?q=dig") == ["spade"]  # in the notes
    assert names("?q=SEEDS") == ["Dibber"]  # in the used-for words
    assert names("?q=zzz") == []
    assert (
        client.get(f"{plot['base']}/equipment?kind=hammer", headers=plot["viewer"]).status_code
        == 422
    )


def test_edit_and_delete(client, plot):  # noqa: F811
    item = add(client, plot).json
    base = f"{plot['base']}/equipment/{item['id']}"
    resp = client.patch(
        base,
        json={"quantity": 3, "status": "out_of_action", "kind": None, "used_for": "dig"},
        headers=plot["editor"],
    )
    assert resp.status_code == 200, resp.json
    assert (
        resp.json["quantity"],
        resp.json["status"],
        resp.json["kind"],
        resp.json["keywords"],
    ) == (
        3,
        "out_of_action",
        None,
        ["dig"],
    )
    assert client.patch(base, json={"quantity": 0}, headers=plot["editor"]).status_code == 422
    assert client.delete(base, headers=plot["editor"]).status_code == 204
    assert client.get(base, headers=plot["editor"]).status_code == 404


def test_where_it_lives(client, plot):  # noqa: F811
    shed = client.post(
        f"{plot['base']}/features",
        json={
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-1.0, 51.0]},
            "properties": {"name": "Shed", "kind": "shed"},
        },
        headers=plot["owner"],
    ).json["id"]
    item = add(client, plot, location_feature_id=shed).json
    assert (item["location_feature_id"], item["location_name"]) == (shed, "Shed")
    listed = client.get(f"{plot['base']}/equipment", headers=plot["viewer"]).json
    assert listed[0]["location_name"] == "Shed"
    client.delete(f"{plot['base']}/features/{shed}", headers=plot["owner"])
    after = client.get(f"{plot['base']}/equipment/{item['id']}", headers=plot["viewer"]).json
    assert after["location_feature_id"] is None  # the shed went; the spade stays


def test_the_location_must_be_in_this_allotment(client, plot, register):  # noqa: F811
    assert add(client, plot, location_feature_id=999999).status_code == 422
    other, _ = register("other@example.com", "Other")
    oid = client.post("/api/v1/allotments", json={"name": "Elsewhere"}, headers=other).json["id"]
    theirs = client.post(
        f"/api/v1/allotments/{oid}/features",
        json={
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [0, 0]},
            "properties": {"kind": "shed"},
        },
        headers=other,
    ).json["id"]
    bad = add(client, plot, location_feature_id=theirs)
    assert bad.status_code == 422 and "allotment" in bad.json["message"]
    item = add(client, plot).json
    patch = client.patch(
        f"{plot['base']}/equipment/{item['id']}",
        json={"location_feature_id": theirs},
        headers=plot["editor"],
    )
    assert patch.status_code == 422


def test_roles_and_isolation(client, plot, register):  # noqa: F811
    assert add(client, plot, who="viewer").status_code == 403
    assert add(client, plot, who="stranger").status_code == 404
    item = add(client, plot).json
    base = f"{plot['base']}/equipment/{item['id']}"
    assert client.get(base, headers=plot["stranger"]).status_code == 404
    assert client.patch(base, json={"quantity": 2}, headers=plot["viewer"]).status_code == 403
    assert client.delete(base, headers=plot["viewer"]).status_code == 403
    assert client.get(f"{plot['base']}/equipment", headers=plot["stranger"]).status_code == 404
    other, _ = register("other@example.com", "Other")
    oid = client.post("/api/v1/allotments", json={"name": "Elsewhere"}, headers=other).json["id"]
    assert (
        client.get(f"/api/v1/allotments/{oid}/equipment/{item['id']}", headers=other).status_code
        == 404
    )
    assert client.get(f"/api/v1/allotments/{oid}/equipment", headers=other).json == []


def test_deleting_the_allotment_removes_its_equipment(client, plot):  # noqa: F811
    add(client, plot)
    assert client.delete(plot["base"], headers=plot["owner"]).status_code in (200, 204)
    assert client.get(f"{plot['base']}/equipment", headers=plot["owner"]).status_code == 404


def test_the_kinds_list(client, plot):  # noqa: F811
    resp = client.get("/api/v1/equipment-kinds", headers=plot["viewer"])
    assert resp.status_code == 200
    by_key = {k["key"]: k["label"] for k in resp.json}
    assert by_key["spade"] == "Spade" and by_key["hand_fork"] == "Hand fork"
    assert client.get("/api/v1/equipment-kinds").status_code == 401


def test_events_are_emitted(client, plot):  # noqa: F811
    seen = []
    events.subscribe(events.WILDCARD, lambda e: seen.append(e.type))
    item = add(client, plot).json
    client.patch(
        f"{plot['base']}/equipment/{item['id']}", json={"quantity": 2}, headers=plot["editor"]
    )
    client.delete(f"{plot['base']}/equipment/{item['id']}", headers=plot["editor"])
    assert [t for t in seen if t.startswith("equipment.")] == [
        "equipment.created",
        "equipment.updated",
        "equipment.deleted",
    ]


@pytest.mark.parametrize("quantity", [1, 6, 100000])
def test_quantities(client, plot, quantity):  # noqa: F811
    assert add(client, plot, quantity=quantity).json["quantity"] == quantity
