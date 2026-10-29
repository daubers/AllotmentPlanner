import math

import pytest

from allotment.gpx import GpxError, outline_from_trace, parse_gpx

LAT, LON = 51.5, -0.12
DLAT = 1 / 111_320
DLON = 1 / (111_320 * math.cos(math.radians(LAT)))


def pt(x, y):
    """A point x metres east and y metres north of the corner."""
    return LAT + y * DLAT, LON + x * DLON


def gpx(points, element="trkpt", ns="http://www.topografix.com/GPX/1/1", wrap=True, extra=""):
    body = "".join(
        f'<{element} lat="{lat:.8f}" lon="{lon:.8f}"><ele>10</ele></{element}>'
        for lat, lon in points
    )
    inner = f"<trkseg>{body}</trkseg>" if element == "trkpt" and wrap else body
    if element == "trkpt":
        inner = f"<trk><name>Plot edge</name>{inner}</trk>"
    elif element == "rtept":
        inner = f"<rte>{inner}</rte>"
    return (
        f'<?xml version="1.0"?><gpx xmlns="{ns}" version="1.1" creator="test">{extra}{inner}</gpx>'
    )


def walk(w=20, h=10, per_side=10, close=True, jitter=0.0):
    """A walk round a w x h metre rectangle, a point every few metres."""
    corners = [(0, 0), (w, 0), (w, h), (0, h)]
    pts = []
    for (x0, y0), (x1, y1) in zip(corners, corners[1:] + [corners[0]], strict=True):
        for i in range(per_side):
            t = i / per_side
            wobble = jitter * math.sin(7 * (len(pts) + 1))
            pts.append(pt(x0 + (x1 - x0) * t + wobble, y0 + (y1 - y0) * t - wobble))
    if close:
        pts.append(pt(0, 0))
    return pts


def test_a_walked_rectangle_becomes_that_rectangle():
    out = outline_from_trace(parse_gpx(gpx(walk())))
    assert out.area_m2 == pytest.approx(200, rel=0.03)
    assert out.perimeter_m == pytest.approx(60, rel=0.03)
    assert out.points_out < out.points_in  # simplified
    assert out.polygon.exterior.is_ccw and out.polygon.is_valid
    assert out.gap_m < 1 and out.warnings == []


def test_wobbly_gps_is_smoothed_without_losing_the_shape():
    out = outline_from_trace(parse_gpx(gpx(walk(jitter=0.25))))
    assert out.area_m2 == pytest.approx(200, rel=0.08)
    assert out.points_out <= 12


def test_both_gpx_versions_and_routes_and_waypoints():
    pts = walk()
    v10 = parse_gpx(gpx(pts, ns="http://www.topografix.com/GPX/1/0"))
    assert v10.kind == "track" and len(v10.points) == len(pts)
    assert parse_gpx(gpx(pts, element="rtept")).kind == "route"
    assert parse_gpx(gpx(pts, element="wpt")).kind == "waypoints"
    assert parse_gpx(gpx(pts).encode()).name == "Plot edge"


def test_a_paused_walk_with_several_segments_is_joined():
    pts = walk()
    half = len(pts) // 2

    def seg(p):
        points = "".join(f'<trkpt lat="{a:.8f}" lon="{b:.8f}"/>' for a, b in p)
        return f"<trkseg>{points}</trkseg>"

    ns = "http://www.topografix.com/GPX/1/1"
    text = f'<gpx xmlns="{ns}"><trk>{seg(pts[:half])}{seg(pts[half:])}</trk></gpx>'
    trace = parse_gpx(text)
    assert trace.segments == 2 and len(trace.points) == len(pts)
    assert outline_from_trace(trace).area_m2 == pytest.approx(200, rel=0.03)


def test_the_longest_of_several_tracks_is_used_and_it_says_so():
    other = gpx(walk(5, 5, per_side=2))
    first = gpx(walk()).replace(
        "</gpx>", other.split("<gpx", 1)[1].split(">", 1)[1].replace("</gpx>", "") + "</gpx>"
    )
    trace = parse_gpx(first)
    assert any("2 tracks" in w for w in trace.warnings)
    assert outline_from_trace(trace).area_m2 > 150


def test_ends_a_little_apart_are_joined_with_a_note_and_far_apart_is_refused():
    near = outline_from_trace(parse_gpx(gpx(walk(close=False)[:-3])))
    assert near.area_m2 > 150
    gappy = walk(close=False)[: len(walk()) - 8]  # stops well short of the start
    with pytest.raises(GpxError, match="from where it started"):
        outline_from_trace(parse_gpx(gpx(gappy)), max_gap_m=3)
    assert any("joined up" in w for w in outline_from_trace(parse_gpx(gpx(gappy))).warnings)


def test_a_figure_of_eight_uses_its_largest_loop():
    pts = [
        pt(0, 0),
        pt(10, 0),
        pt(10, 10),
        pt(0, 10),
        pt(0, 3),
        pt(-8, 3),
        pt(-8, 7),
        pt(0, 7),
        pt(0, 0),
    ]
    out = outline_from_trace(parse_gpx(gpx(pts)), simplify_m=0.01)
    assert out.polygon.is_valid
    assert any("crosses itself" in w for w in out.warnings)


def test_too_small_and_too_big_are_refused():
    with pytest.raises(GpxError, match="too small"):
        outline_from_trace(parse_gpx(gpx(walk(1, 1, per_side=3))))
    with pytest.raises(GpxError, match="not a plot"):
        outline_from_trace(parse_gpx(gpx(walk(2000, 1500, per_side=3))), max_gap_m=10_000)


def test_few_points_are_allowed_with_a_warning():
    pts = [pt(0, 0), pt(20, 0), pt(20, 10), pt(0, 10), pt(0, 0)]
    out = outline_from_trace(parse_gpx(gpx(pts)))
    assert out.area_m2 == pytest.approx(200, rel=0.02)
    assert any("Few points" in w for w in out.warnings)


@pytest.mark.parametrize(
    ("text", "why"),
    [
        ("not xml at all", "readable"),
        ("<html><body/></html>", "not a GPX"),
        ('<gpx xmlns="x"></gpx>', "no track"),
        (
            '<gpx><trk><trkseg><trkpt lat="1" lon="1"/></trkseg></trk></gpx>',
            "too few",
        ),
        ('<!DOCTYPE gpx [<!ENTITY a "aaaa">]><gpx/>', "plain GPX"),
    ],
)
def test_unusable_files_say_why(text, why):
    with pytest.raises(GpxError, match=why):
        parse_gpx(text)


def test_a_huge_file_is_refused_before_it_is_parsed():
    with pytest.raises(GpxError, match="too big"):
        parse_gpx(b"<gpx>" + b" " * (6 * 1024 * 1024) + b"</gpx>")


def test_points_outside_the_world_are_ignored():
    bad = '<gpx><trk><trkseg><trkpt lat="95" lon="0"/><trkpt lat="x" lon="0"/></trkseg></trk></gpx>'
    with pytest.raises(GpxError, match="no track"):
        parse_gpx(bad)
