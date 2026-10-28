import math

import numpy as np
from shapely.geometry import Polygon

from allotment import boundary as bd

LENGTH, WIDTH = 20.0, 8.0
THETA = math.radians(25)
CENTRE = np.array([3.0, -2.0])
U = np.array([math.cos(THETA), math.sin(THETA)])
V = np.array([-math.sin(THETA), math.cos(THETA)])


def at(u, v):
    return CENTRE + U * u + V * v


def posts(a, b, spacing, rng, noise=0.12):
    """Fence posts along the segment a-b, a little off the line like real posts."""
    n = max(2, int(np.linalg.norm(b - a) / spacing) + 1)
    return np.array([a + (b - a) * t + rng.normal(0, noise, 2) for t in np.linspace(0, 1, n)])


def truth() -> Polygon:
    return Polygon(
        [
            at(-LENGTH / 2, -WIDTH / 2),
            at(LENGTH / 2, -WIDTH / 2),
            at(LENGTH / 2, WIDTH / 2),
            at(-LENGTH / 2, WIDTH / 2),
        ]
    )


def overlap(corners) -> float:
    found, real = Polygon(corners), truth()
    return found.intersection(real).area / found.union(real).area


def inside_points(rng, n=30):
    """Where cameras stood and objects were found: spread over most of the plot."""
    return np.array([at(rng.uniform(-8, 8), rng.uniform(-3, 3)) for _ in range(n)])


def sides(rng, which=("south", "north", "west", "east")):
    h, w = LENGTH / 2, WIDTH / 2
    seg = {
        "south": (at(-h, -w), at(h, -w)),
        "north": (at(-h, w), at(h, w)),
        "west": (at(-h, -w), at(-h, w)),
        "east": (at(h, -w), at(h, w)),
    }
    return np.vstack([posts(*seg[s], 2.0, rng) for s in which])


def test_a_fully_fenced_plot_is_recovered():
    rng = np.random.default_rng(1)
    result = bd.fit_boundary(sides(rng), inside_points(rng))
    assert result is not None and result.sides_found == 4 and result.complete
    assert overlap(result.corners) > 0.93
    assert math.degrees(abs(((result.angle - THETA + math.pi / 2) % math.pi) - math.pi / 2)) < 4


def test_a_neighbours_fence_and_a_fence_through_the_plot_are_not_mistaken_for_the_edge():
    rng = np.random.default_rng(2)
    neighbour = posts(
        at(-8, WIDTH / 2 + 3), at(8, WIDTH / 2 + 3), 2.5, rng
    )  # 3 m beyond the north side
    internal = posts(at(-3, 0), at(3, 0), 1.5, rng)  # round a bed, cameras on both sides of it
    result = bd.fit_boundary(np.vstack([sides(rng), neighbour, internal]), inside_points(rng))
    assert result.sides_found == 4
    assert overlap(result.corners) > 0.9


def test_a_side_that_was_never_photographed_is_guessed_and_flagged():
    rng = np.random.default_rng(3)
    result = bd.fit_boundary(sides(rng, ("south", "north", "west")), inside_points(rng))
    assert result.sides_found == 3 and not result.complete
    assert (
        overlap(result.corners) > 0.7
    )  # the missing end is only as good as the photographed extent


def test_two_long_sides_are_enough_to_propose_something():
    rng = np.random.default_rng(4)
    result = bd.fit_boundary(sides(rng, ("south", "north")), inside_points(rng))
    assert result is not None and result.sides_found == 2
    assert Polygon(result.corners).intersection(truth()).area > 0.6 * truth().area


def test_not_enough_evidence_gives_nothing():
    rng = np.random.default_rng(5)
    inside = inside_points(rng)
    assert bd.fit_boundary(sides(rng, ("south",)), inside) is None  # one fence is not a plot
    assert bd.fit_boundary(rng.uniform(-10, 10, (40, 2)), inside) is None  # scatter, no lines
    assert bd.fit_boundary(np.zeros((2, 2)), inside) is None  # too few points
    assert bd.fit_boundary(sides(rng), np.zeros((0, 2))) is None  # nothing known to be inside


def test_fences_at_odd_angles_are_ignored():
    rng = np.random.default_rng(6)
    diagonal = posts(at(-6, -3), at(6, 3), 1.5, rng)
    result = bd.fit_boundary(np.vstack([sides(rng), diagonal]), inside_points(rng))
    assert result.sides_found == 4 and overlap(result.corners) > 0.9


def test_a_few_stray_detections_do_not_move_the_edges():
    rng = np.random.default_rng(7)
    strays = rng.uniform(-15, 15, (6, 2)) + CENTRE
    result = bd.fit_boundary(np.vstack([sides(rng), strays]), inside_points(rng))
    assert result.sides_found == 4 and overlap(result.corners) > 0.9


def test_the_same_input_gives_the_same_answer():
    pts, inside = sides(np.random.default_rng(8)), inside_points(np.random.default_rng(9))
    a, b = bd.fit_boundary(pts, inside), bd.fit_boundary(pts, inside)
    assert a.corners == b.corners
