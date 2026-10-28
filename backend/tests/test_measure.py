import math

import numpy as np
import pytest

from allotment import measure


def area(xy):
    x, y = xy[:, 0], xy[:, 1]
    return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))


def polygon_constraints(sides, diagonal):
    """Edges 1-2, 2-3, 3-4, 4-1 of a quadrilateral plus the 1-3 diagonal."""
    return [
        (0, 1, sides[0]),
        (1, 2, sides[1]),
        (2, 3, sides[2]),
        (3, 0, sides[3]),
        (0, 2, diagonal),
    ]


# A bed that was drawn a bit skewed, 10 x 5 in fact.
DRAWN = np.array([[0.0, 0.0], [10.6, 0.4], [10.1, 5.7], [-0.3, 4.6]])


def test_a_skewed_rectangle_becomes_exactly_10_by_5():
    fit = measure.fit_shape(
        DRAWN, polygon_constraints([10, 5, 10, 5], math.hypot(10, 5)), closed=True
    )
    assert np.abs(fit.after).max() < 1e-3
    assert np.abs(fit.before).max() > 0.3
    assert fit.missing == 0 and fit.recheck == []
    sides = [np.linalg.norm(fit.xy[i] - fit.xy[(i + 1) % 4]) for i in range(4)]
    assert sides == pytest.approx([10, 5, 10, 5], abs=1e-3)


def test_the_result_is_not_flipped_or_swung_round():
    fit = measure.fit_shape(
        DRAWN, polygon_constraints([10, 5, 10, 5], math.hypot(10, 5)), closed=True
    )
    assert math.copysign(1, area(fit.xy)) == math.copysign(
        1, area(DRAWN)
    )  # same winding: no mirror
    # Still roughly where it was drawn: corner 1 has hardly moved, edge 1 points the same way.
    assert np.linalg.norm(fit.xy[0] - DRAWN[0]) < 1.0
    drawn_dir = math.atan2(*(DRAWN[1] - DRAWN[0])[::-1])
    fitted_dir = math.atan2(*(fit.xy[1] - fit.xy[0])[::-1])
    assert abs(drawn_dir - fitted_dir) < 0.2


def test_a_trapezoid_is_fitted():
    drawn = np.array([[0, 0], [8, 0.3], [6.1, 3.2], [1.8, 2.9]], dtype=float)
    top, bottom, height = 4.0, 8.0, 3.0
    side = math.hypot(2.0, height)
    diagonal = math.hypot(6.0, height)
    fit = measure.fit_shape(
        drawn, polygon_constraints([bottom, side, top, side], diagonal), closed=True
    )
    assert np.abs(fit.after).max() < 1e-3
    assert abs(abs(area(fit.xy)) - (top + bottom) / 2 * height) < 0.01


def test_one_wrong_measurement_is_flagged_when_there_is_a_spare_one():
    constraints = polygon_constraints([10, 5, 10, 5], math.hypot(10, 5))
    constraints.append((1, 3, math.hypot(10, 5)))  # the other diagonal, a spare measurement
    constraints[1] = (1, 2, 7.0)  # side 2-3 mis-read as 7 instead of 5
    fit = measure.fit_shape(DRAWN, constraints, closed=True)
    assert fit.recheck, "the disagreement should show up"
    assert max(abs(fit.after)) > 0.15


def test_an_underdetermined_shape_says_what_is_missing():
    edges_only = [(0, 1, 10.0), (1, 2, 5.0), (2, 3, 10.0), (3, 0, 5.0)]
    fit = measure.fit_shape(DRAWN, edges_only, closed=True)
    assert fit.missing == 1  # a quadrilateral needs 5 distances
    one_edge = measure.fit_shape(DRAWN, [(0, 1, 10.0)], closed=True)
    assert one_edge.missing == 4
    # ... and with nothing more to go on, unmeasured corners stay where they were drawn.
    assert np.linalg.norm(one_edge.xy[2] - DRAWN[2]) < 0.2


def test_a_line_is_stretched_segment_by_segment():
    drawn = np.array([[0, 0], [5.4, 0], [5.4, 6.3]], dtype=float)
    fit = measure.fit_shape(drawn, [(0, 1, 5.0), (1, 2, 6.0)], closed=False)
    assert np.linalg.norm(fit.xy[0] - fit.xy[1]) == pytest.approx(5.0, abs=1e-3)
    assert np.linalg.norm(fit.xy[1] - fit.xy[2]) == pytest.approx(6.0, abs=1e-3)
    assert fit.missing == 0


def test_expected_distances_for_each_shape():
    square = measure.expected("Polygon", 4, None)
    assert [(s.kind, s.a, s.b) for s in square] == [
        ("edge", 0, 1), ("edge", 1, 2), ("edge", 2, 3), ("edge", 3, 0), ("diagonal", 0, 2),
    ]  # fmt: skip
    assert len(measure.expected("Polygon", 3, None)) == 3  # a triangle needs no diagonal
    assert len(measure.expected("Polygon", 6, None)) == 2 * 6 - 3
    assert [s.kind for s in measure.expected("LineString", 3, None)] == ["edge", "edge"]
    assert [s.kind for s in measure.expected("Point", 1, 2.0)] == ["radius"]
    assert measure.expected("Point", 1, None) == []


def test_corners_drop_the_closing_point_and_projection_round_trips():
    ring = {
        "type": "Polygon",
        "coordinates": [[[-1, 51], [-1, 51.001], [-0.999, 51.001], [-1, 51]]],
    }
    pts = measure.corners(ring)
    assert len(pts) == 3
    origin = measure.centre(pts)
    xy = measure.to_metres(pts, origin)
    assert abs(np.linalg.norm(xy[0] - xy[1]) - 111.2) < 0.5  # 0.001 degrees of latitude
    back = measure.from_metres(xy, origin)
    assert np.array(back) == pytest.approx(np.array(pts), abs=1e-9)
