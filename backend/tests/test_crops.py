from datetime import date

from allotment import crops


def test_every_crop_is_sane():
    assert len(crops.CROPS) >= 30
    for key, c in crops.CROPS.items():
        assert key == c.key
        assert c.method_default in crops.METHODS, key
        assert c.spacing_plant_cm > 0 and c.spacing_row_cm > 0, key
        assert 0 < c.maturity_days_min <= c.maturity_days_max, key
        for months in (c.sow_months, c.plant_out_months, c.harvest_months):
            assert all(1 <= m <= 12 for m in months), key
            assert len(set(months)) == len(months), key
        assert c.sow_months and c.harvest_months, key
        if c.method_default == "transplant":
            assert c.plant_out_months, f"{key} is a transplant crop with no plant-out months"
        else:
            assert not c.plant_out_months, f"{key} is direct sown but has plant-out months"
        assert c.succession_days is None or c.succession_days > 0, key


def test_span_wraps_the_new_year():
    assert crops._span(3, 5) == (3, 4, 5)
    assert crops._span(11, 2) == (11, 12, 1, 2)
    assert crops._span(7, 7) == (7,)


def test_next_in_window_stays_put_inside_the_window():
    assert crops.next_in_window((3, 4, 5), date(2026, 4, 17)) == date(2026, 4, 17)


def test_next_in_window_waits_for_the_next_month():
    assert crops.next_in_window((3, 4, 5), date(2026, 1, 20)) == date(2026, 3, 1)


def test_next_in_window_rolls_into_next_year():
    assert crops.next_in_window((11, 12, 1, 2), date(2026, 8, 10)) == date(2026, 11, 1)
    assert crops.next_in_window((2, 3), date(2026, 12, 5)) == date(2027, 2, 1)


def test_next_in_window_with_no_months():
    assert crops.next_in_window((), date(2026, 1, 1)) is None


def test_get_and_search():
    assert crops.get_crop("lettuce").name == "Lettuce"
    assert crops.get_crop("nope") is None and crops.get_crop(None) is None
    names = [c.key for c in crops.search("bean")]
    assert {"broad_bean", "runner_bean", "french_bean"} <= set(names)
    assert crops.search("brassicaceae")  # by family
    assert crops.search("  LETTUCE ")[0].key == "lettuce"
    assert crops.search("zzz") == []
    assert [c.name for c in crops.search()] == sorted(c.name for c in crops.CROPS.values())


def test_crops_endpoint(client, register):
    headers, _ = register()
    everything = client.get("/api/v1/crops", headers=headers)
    assert everything.status_code == 200
    assert len(everything.json) == len(crops.CROPS)
    found = client.get("/api/v1/crops?q=carrot", headers=headers).json
    assert [c["key"] for c in found] == ["carrot"]
    carrot = found[0]
    assert carrot["spacing_plant_cm"] == 5 and carrot["spacing_row_cm"] == 25
    assert carrot["sow_months"] == [3, 4, 5, 6, 7]
    assert carrot["plant_out_months"] == []


def test_crops_need_a_login(client):
    assert client.get("/api/v1/crops").status_code == 401
