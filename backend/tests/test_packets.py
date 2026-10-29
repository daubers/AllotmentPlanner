import io

from allotment import events

from .helpers import make_jpeg
from .test_media import plot  # noqa: F401 - the shared allotment with an owner, editor and viewer


def make(client, plot, who="editor", **body):  # noqa: F811
    body.setdefault("name", "Tomato")
    return client.post(f"{plot['base']}/packets", json=body, headers=plot[who])


def test_create_defaults_and_read_back(client, plot):  # noqa: F811
    resp = make(client, plot, variety="Moneymaker", calendar={"sow_indoors": [3, 2]})
    assert resp.status_code == 201
    p = resp.json
    assert p["name"] == "Tomato" and p["variety"] == "Moneymaker"
    assert p["stock"] == "full" and p["status"] == "active" and p["photos"] == []
    assert p["calendar"] == {
        "sow_indoors": [2, 3],
        "sow_outdoors": [],
        "plant_out": [],
        "harvest": [],
    }
    got = client.get(f"{plot['base']}/packets/{p['id']}", headers=plot["viewer"])
    assert got.status_code == 200 and got.json["name"] == "Tomato"


def test_roles(client, plot):  # noqa: F811
    assert make(client, plot, who="viewer").status_code == 403
    assert make(client, plot, who="stranger").status_code == 404
    pid = make(client, plot).json["id"]
    url = f"{plot['base']}/packets/{pid}"
    assert client.patch(url, json={"notes": "x"}, headers=plot["viewer"]).status_code == 403
    assert client.delete(url, headers=plot["viewer"]).status_code == 403
    assert client.get(url, headers=plot["stranger"]).status_code == 404


def test_validation(client, plot):  # noqa: F811
    assert make(client, plot, name="").status_code == 422
    assert make(client, plot, stock="lots").status_code == 422
    assert make(client, plot, sun="moon").status_code == 422
    assert make(client, plot, calendar={"harvest": [13]}).status_code == 422
    bad = make(client, plot, germinate_days_min=20, germinate_days_max=7)
    assert bad.status_code == 422 and "germinate" in bad.json["message"]
    assert client.get(f"{plot['base']}/packets", headers=plot["owner"]).json == []  # nothing saved


def test_patch_changes_only_what_is_sent_and_rechecks_ranges(client, plot):  # noqa: F811
    pid = make(client, plot, supplier="Thompson", maturity_days_min=60, maturity_days_max=90).json[
        "id"
    ]
    url = f"{plot['base']}/packets/{pid}"
    out = client.patch(url, json={"stock": "low", "sun": "full"}, headers=plot["editor"]).json
    assert (out["stock"], out["sun"], out["supplier"]) == ("low", "full", "Thompson")
    bad = client.patch(url, json={"maturity_days_max": 30}, headers=plot["editor"])
    assert bad.status_code == 422
    assert client.get(url, headers=plot["owner"]).json["maturity_days_max"] == 90
    cleared = client.patch(
        url, json={"sun": None, "best_before_year": None}, headers=plot["editor"]
    )
    assert cleared.json["sun"] is None


def test_search_and_stock_filter(client, plot):  # noqa: F811
    make(client, plot, name="Tomato", variety="Moneymaker", supplier="Suttons")
    make(client, plot, name="Carrot", variety="Nantes", latin_name="Daucus carota", stock="low")
    make(client, plot, name="Beetroot", notes="good with tomato sauce")
    names = lambda **q: [  # noqa: E731
        p["name"]
        for p in client.get(f"{plot['base']}/packets", query_string=q, headers=plot["viewer"]).json
    ]
    assert names() == ["Beetroot", "Carrot", "Tomato"]
    assert names(q="tomato") == ["Beetroot", "Tomato"]
    assert names(q="DAUCUS") == ["Carrot"]
    assert names(q="suttons") == ["Tomato"]
    assert names(stock="low") == ["Carrot"]


def test_what_can_i_sow_this_month(client, plot):  # noqa: F811
    make(client, plot, name="Tomato", calendar={"sow_indoors": [2, 3], "harvest": [8, 9]})
    make(client, plot, name="Carrot", calendar={"sow_outdoors": [3, 4, 5]})
    make(client, plot, name="Kale", calendar={"plant_out": [5]})
    get = lambda **q: sorted(  # noqa: E731
        p["name"]
        for p in client.get(f"{plot['base']}/packets", query_string=q, headers=plot["viewer"]).json
    )
    assert get(month=3) == ["Carrot", "Tomato"]
    assert get(month=2) == ["Tomato"]
    assert get(month=9) == []
    assert get(month=9, activity="harvest") == ["Tomato"]
    assert get(month=5, activity="plant_out") == ["Kale"]
    assert get(month=3, q="carr") == ["Carrot"]
    assert client.get(f"{plot['base']}/packets?month=13", headers=plot["viewer"]).status_code == 422


def test_packets_are_per_allotment(client, plot, register):  # noqa: F811
    pid = make(client, plot).json["id"]
    other, _ = register("other@example.com", "Other")
    oid = client.post("/api/v1/allotments", json={"name": "Elsewhere"}, headers=other).json["id"]
    assert client.get(f"/api/v1/allotments/{oid}/packets", headers=other).json == []
    assert client.get(f"/api/v1/allotments/{oid}/packets/{pid}", headers=other).status_code == 404


def test_photos_link_to_a_packet_and_survive_its_deletion(client, plot):  # noqa: F811
    pid = make(client, plot).json["id"]
    up = client.post(
        plot["url"],
        data={"file": (io.BytesIO(make_jpeg()), "front.jpg"), "packet_id": str(pid)},
        headers=plot["editor"],
        content_type="multipart/form-data",
    )
    assert up.status_code == 201 and up.json["packet_id"] == pid
    packet = client.get(f"{plot['base']}/packets/{pid}", headers=plot["viewer"]).json
    assert [m["id"] for m in packet["photos"]] == [up.json["id"]]
    listed = client.get(f"{plot['url']}?packet_id={pid}", headers=plot["viewer"]).json
    assert [m["id"] for m in listed] == [up.json["id"]]
    assert client.delete(f"{plot['base']}/packets/{pid}", headers=plot["editor"]).status_code == 204
    after = client.get(f"{plot['url']}/{up.json['id']}", headers=plot["viewer"]).json
    assert after["packet_id"] is None


def test_a_photo_cannot_name_another_allotments_packet(client, plot, register):  # noqa: F811
    other, _ = register("other@example.com", "Other")
    oid = client.post("/api/v1/allotments", json={"name": "Elsewhere"}, headers=other).json["id"]
    foreign = client.post(
        f"/api/v1/allotments/{oid}/packets", json={"name": "Theirs"}, headers=other
    ).json["id"]
    up = client.post(
        plot["url"],
        data={"file": (io.BytesIO(make_jpeg()), "x.jpg"), "packet_id": str(foreign)},
        headers=plot["editor"],
        content_type="multipart/form-data",
    )
    assert up.status_code == 422


def test_events(client, plot):  # noqa: F811
    seen = []
    events.subscribe("*", lambda e: seen.append(e.type))
    pid = make(client, plot).json["id"]
    client.patch(f"{plot['base']}/packets/{pid}", json={"notes": "n"}, headers=plot["editor"])
    client.delete(f"{plot['base']}/packets/{pid}", headers=plot["editor"])
    assert [t for t in seen if t.startswith("packet.")] == [
        "packet.created",
        "packet.updated",
        "packet.deleted",
    ]
