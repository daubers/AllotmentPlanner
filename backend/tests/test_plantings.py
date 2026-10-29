import pytest

from allotment.plantings import (
    PlantOutError,
    area_m2,
    overlap_warning,
    overlaps,
    plant_out_groups,
    region_problem,
    to_polygon,
)

LAT = 51.0
DLAT = 1 / 111_320  # one metre of latitude
DLON = 1 / (111_320 * 0.629)  # one metre of longitude at 51 degrees north


def rect(x0, y0, x1, y1, lon0=-1.0, lat0=LAT):
    """A rectangle ``x0..x1`` metres east and ``y0..y1`` metres north of a corner."""
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
    return {
        "type": "Polygon",
        "coordinates": [[[lon0 + x * DLON, lat0 + y * DLAT] for x, y in pts]],
    }


BED = rect(0, 0, 4, 1.2)  # a 4 m by 1.2 m bed


def test_area_in_square_metres():
    assert area_m2(to_polygon(BED)) == pytest.approx(4.8, rel=0.02)


@pytest.mark.parametrize(
    ("region", "ok"),
    [
        (rect(0.5, 0.2, 1.5, 1.0), True),
        (rect(0, 0, 4, 1.2), True),  # the whole bed
        (rect(-0.2, 0.0, 1.0, 1.0), True),  # 20 cm over the edge is forgiven
        (rect(3.5, 0.2, 4.8, 1.0), False),  # 80 cm over the end
        (rect(10, 10, 11, 11), False),  # somewhere else
    ],
)
def test_a_region_must_lie_inside_the_bed(region, ok):
    assert (region_problem(region, BED) is None) is ok


def test_bad_regions_are_explained():
    assert "polygon" in region_problem({"type": "Point", "coordinates": [0, 0]}, BED)
    assert "outside" in region_problem(rect(9, 9, 10, 10), BED)
    assert "area" in region_problem(rect(0, 0, 1, 1), {"type": "Point", "coordinates": [0, 0]})
    bowtie = {
        "type": "Polygon",
        "coordinates": [
            [[-1, LAT], [-0.99999, LAT + 1e-5], [-1, LAT + 1e-5], [-0.99999, LAT], [-1, LAT]]
        ],
    }
    assert "crosses" in region_problem(bowtie, BED)
    assert "small" in region_problem(rect(1, 0.5, 1.02, 0.52), BED)


def test_overlaps_are_found_with_their_size_and_touching_edges_are_not():
    others = [
        (1, "Carrots", rect(0, 0, 2, 1)),
        (2, "Beans", rect(2, 0, 4, 1)),
        (3, "Far", rect(8, 8, 9, 9)),
    ]
    found = overlaps(rect(1, 0, 3, 1), others)
    assert [(i, label) for i, label, _ in found] == [(1, "Carrots"), (2, "Beans")]
    assert all(shared == pytest.approx(1.0, rel=0.05) for _, _, shared in found)
    assert (
        overlaps(rect(2, 0, 3, 1), [(1, "Carrots", rect(0, 0, 2, 1))]) == []
    )  # only an edge in common
    assert overlap_warning("Carrots", 1.0) == "Overlaps Carrots by 1 m²"
    assert overlaps({"type": "Point", "coordinates": [0, 0]}, others) == []


def test_plant_out_groups_cells_by_packet():
    cells = [
        {"row": 0, "col": 0, "status": "germinated", "packet_id": 7},
        {"row": 0, "col": 1, "status": "sown", "packet_id": 7},
        {"row": 1, "col": 0, "status": "germinated", "packet_id": 9},
        {"row": 1, "col": 1, "status": "germinated", "packet_id": None},
    ]
    groups = plant_out_groups(cells)
    assert {k: len(v) for k, v in groups.items()} == {7: 2, 9: 1, None: 1}


@pytest.mark.parametrize(
    ("cell", "message"),
    [
        ({"row": 2, "col": 3, "status": None}, "Row 3, column 4: nothing is sown"),
        ({"row": 0, "col": 0, "status": "failed", "packet_id": 1}, "did not come up"),
        ({"row": 0, "col": 0, "status": "planted_out", "packet_id": 1}, "already planted out"),
    ],
)
def test_cells_that_cannot_be_planted_out_are_named(cell, message):
    with pytest.raises(PlantOutError, match=message):
        plant_out_groups([{"row": 0, "col": 0, "status": "germinated", "packet_id": 1}, cell])


def test_nothing_chosen_is_refused():
    with pytest.raises(PlantOutError):
        plant_out_groups([])
