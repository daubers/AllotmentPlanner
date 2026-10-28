"""Fit the outline of a plot to fence posts and fence lines found on the ground.

The input is a cloud of ground points (east, north metres) where the detector saw posts and the
foot of fences, plus the places we know are *inside* the plot (where the cameras stood, and the
objects found). Plots are almost always rectangles, so:

1. find straight lines in the cloud (RANSAC), keeping only long ones with several points on them;
2. keep the lines that run along, or across, the dominant direction (fences between neighbours
   run along the plot; anything at an odd angle is something else);
3. on each of the four sides, take the *nearest line that lies beyond everything known to be
   inside*. A fence cutting through the plot (round a bed) has cameras on both sides of it, so it is
   skipped; a neighbour's fence further out is passed over in favour of the plot's own;
4. a side with no such line is guessed from how far the photographed area reaches, plus a margin,
   and reported as guessed.
"""

import math
from dataclasses import dataclass

import numpy as np

LINE_TOLERANCE_M = 0.35
MIN_LINE_POINTS = 4
MIN_LINE_LENGTH_M = 3.0
ANGLE_TOLERANCE_DEG = 12.0
GUESS_MARGIN_M = 1.5
MAX_LINES = 10


@dataclass
class Line:
    point: np.ndarray  # a point on the line
    direction: np.ndarray  # unit vector along it
    inliers: np.ndarray  # indices into the point cloud

    @property
    def normal(self) -> np.ndarray:
        return np.array([-self.direction[1], self.direction[0]])

    @property
    def angle(self) -> float:
        """Direction in radians, folded into [0, pi) because a line has no front or back."""
        return math.atan2(self.direction[1], self.direction[0]) % math.pi


@dataclass
class Boundary:
    corners: list[tuple[float, float]]  # four (east, north) corners, in order
    sides_found: int  # how many of the four sides came from fences (the rest are guessed)
    support: int  # fence points on the sides that were found
    angle: float  # direction of the long axis, radians

    @property
    def complete(self) -> bool:
        return self.sides_found == 4


def _fit(points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    centre = points.mean(axis=0)
    _, _, vt = np.linalg.svd(points - centre, full_matrices=False)
    return centre, vt[0]


def _same_line(a: Line, b: Line, tolerance: float) -> bool:
    gap = abs(a.angle - b.angle) % math.pi
    if min(gap, math.pi - gap) > math.radians(4):
        return False
    return abs(float((b.point - a.point) @ a.normal)) < tolerance * 2


def find_lines(
    points: np.ndarray, rng: np.random.Generator, tolerance: float = LINE_TOLERANCE_M
) -> list[Line]:
    """Long, well-supported straight lines in the cloud (RANSAC, strongest first).

    Points are not removed once they are on a line: a corner post belongs to two sides, and taking
    it away would leave a short side with too few points. Duplicates are rejected instead."""
    lines: list[Line] = []
    n = len(points)
    for _ in range(MAX_LINES):
        best: np.ndarray | None = None
        for _ in range(300):
            i, j = rng.choice(n, 2, replace=False)
            d = points[j] - points[i]
            length = np.linalg.norm(d)
            if length < 1.0:
                continue
            d = d / length
            dist = np.abs((points - points[i]) @ np.array([-d[1], d[0]]))
            inliers = np.flatnonzero(dist < tolerance)
            if len(inliers) < MIN_LINE_POINTS or (best is not None and len(inliers) <= len(best)):
                continue
            centre, direction = _fit(points[inliers])
            candidate = Line(centre, direction, inliers)
            if np.ptp((points[inliers] - centre) @ direction) < MIN_LINE_LENGTH_M:
                continue
            if any(_same_line(candidate, known, tolerance) for known in lines):
                continue
            best = inliers
        if best is None:
            break
        centre, direction = _fit(points[best])
        dist = np.abs((points - centre) @ np.array([-direction[1], direction[0]]))
        lines.append(Line(centre, direction, np.flatnonzero(dist < tolerance)))
    return _without_echoes(lines)


def _without_echoes(lines: list[Line], overlap: float = 0.5) -> list[Line]:
    """Drop a line that mostly re-uses the points of a stronger one: it is the same fence seen at a
    slightly wrong angle, not another fence. (Two sides sharing a corner post overlap by one point,
    far below this.)"""
    kept: list[Line] = []
    for ln in sorted(lines, key=lambda ln: -len(ln.inliers)):
        mine = set(ln.inliers.tolist())
        if all(len(mine & set(k.inliers.tolist())) / len(mine) < overlap for k in kept):
            kept.append(ln)
    return kept


def _angle_gap(a: float, b: float) -> float:
    d = abs(a - b) % math.pi
    return min(d, math.pi - d)


def fit_boundary(points: np.ndarray, inside: np.ndarray, seed: int = 0) -> Boundary | None:
    """The plot's outline, or None if there is too little to go on."""
    points, inside = (
        np.asarray(points, float).reshape(-1, 2),
        np.asarray(inside, float).reshape(-1, 2),
    )
    if len(points) < MIN_LINE_POINTS or len(inside) == 0:
        return None
    lines = find_lines(points, np.random.default_rng(seed))
    if not lines:
        return None
    main = max(
        lines, key=lambda ln: len(ln.inliers)
    )  # the strongest line sets the plot's direction
    theta = main.angle
    tol = math.radians(ANGLE_TOLERANCE_DEG)
    along = [ln for ln in lines if _angle_gap(ln.angle, theta) < tol]
    across = [ln for ln in lines if _angle_gap(ln.angle, theta + math.pi / 2) < tol]

    u = np.array([math.cos(theta), math.sin(theta)])  # along the plot
    v = np.array([-math.sin(theta), math.cos(theta)])  # across it
    inside_u, inside_v = inside @ u, inside @ v

    def pick(
        lines_: list[Line], axis: np.ndarray, extent: tuple[float, float]
    ) -> tuple[float | None, float | None, int]:
        """Nearest line beyond the inside extent on each side of the axis: (low, high, points)."""
        lo = hi = None
        support = 0
        best_lo = best_hi = None
        for ln in lines_:
            pos = float(ln.point @ axis)
            if pos <= extent[0] + 0.2 and (best_lo is None or pos > best_lo[0]):
                best_lo = (pos, len(ln.inliers))
            if pos >= extent[1] - 0.2 and (best_hi is None or pos < best_hi[0]):
                best_hi = (pos, len(ln.inliers))
        if best_lo:
            lo, support = best_lo[0], support + best_lo[1]
        if best_hi:
            hi, support = best_hi[0], support + best_hi[1]
        return lo, hi, support

    v_lo, v_hi, v_support = pick(along, v, (inside_v.min(), inside_v.max()))
    u_lo, u_hi, u_support = pick(across, u, (inside_u.min(), inside_u.max()))
    found = sum(x is not None for x in (v_lo, v_hi, u_lo, u_hi))
    if found < 2:
        return None  # one fence line doesn't make a plot
    v_lo = v_lo if v_lo is not None else inside_v.min() - GUESS_MARGIN_M
    v_hi = v_hi if v_hi is not None else inside_v.max() + GUESS_MARGIN_M
    u_lo = u_lo if u_lo is not None else inside_u.min() - GUESS_MARGIN_M
    u_hi = u_hi if u_hi is not None else inside_u.max() + GUESS_MARGIN_M
    corners = [u * a + v * b for a, b in ((u_lo, v_lo), (u_hi, v_lo), (u_hi, v_hi), (u_lo, v_hi))]
    return Boundary(
        [(float(c[0]), float(c[1])) for c in corners], found, v_support + u_support, theta
    )
