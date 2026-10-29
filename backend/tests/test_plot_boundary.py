from dataclasses import dataclass

import pytest

from allotment.plot_boundary import belongs, check_cameras, keep_inside, to_enu

REF = (51.5, -0.12)  # lat, lon
M_LAT = 111_132.0
M_LON = 111_412.84 * 0.6225  # at 51.5 degrees


@dataclass
class Obj:
    x: float
    y: float
    width: float = 1.0
    depth: float = 1.0
    label: str = "thing"


def boundary(x0=0, y0=0, x1=20, y1=10):
    """A GeoJSON polygon for a rectangle given in metres east/north of the reference point."""
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
    ring = [[REF[1] + x / M_LON, REF[0] + y / M_LAT] for x, y in pts]
    return {"type": "Polygon", "coordinates": [ring]}


POLY = to_enu(boundary(), REF)


def test_the_boundary_is_converted_to_metres():
    assert POLY.area == pytest.approx(200, rel=0.01)
    minx, miny, maxx, maxy = POLY.bounds
    assert (minx, miny) == (pytest.approx(0, abs=0.05), pytest.approx(0, abs=0.05))
    assert (maxx, maxy) == (pytest.approx(20, rel=0.01), pytest.approx(10, rel=0.01))


@pytest.mark.parametrize(
    ("obj", "expected"),
    [
        (Obj(10, 5), True),  # in the middle
        (Obj(20.8, 5), True),  # just over the edge: GPS wobble
        (Obj(23, 5), False),  # a neighbour's shed
        (Obj(21.5, 5, width=4, depth=4), True),  # a big thing half in
        (Obj(24, 5, width=4, depth=4), False),  # a big thing next door
        (Obj(-8, -8), False),
    ],
)
def test_what_belongs_to_the_plot(obj, expected):
    assert belongs(POLY, obj) is expected


def test_keep_inside_splits_the_objects():
    shed, tree, butt = Obj(5, 5, label="shed"), Obj(40, 5, label="tree"), Obj(15, 8, label="butt")
    kept, dropped = keep_inside(POLY, [shed, tree, butt])
    assert [o.label for o in kept] == ["shed", "butt"]
    assert [o.label for o in dropped] == ["tree"]
    assert keep_inside(POLY, []) == ([], [])


def test_cameras_in_and_around_the_plot_agree_with_the_boundary():
    cams = [(2, 2), (10, 5), (18, 8), (22, 5), (-2, 5)]  # two just outside: fine
    check = check_cameras(POLY, cams)
    assert check.inside == 5 and check.agrees and check.message() is None


def test_cameras_mostly_outside_are_reported_with_how_far():
    check = check_cameras(POLY, [(60, 5), (62, 6), (65, 4), (10, 5)])
    assert not check.agrees and check.inside == 1
    assert "1 of 4" in check.message() and "m off" in check.message()
    assert check.offset_m == pytest.approx(29, abs=2)  # centre at x=49, edge at x=20


def test_no_cameras_is_not_a_disagreement():
    check = check_cameras(POLY, [])
    assert check.agrees and check.message() is None and check.fraction == 1.0
