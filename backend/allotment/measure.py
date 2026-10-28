"""The measuring checklist: which distances to take for each drawn shape, and how to correct the
shape from what was measured.

A polygon with n corners is fixed exactly (up to moving or turning it) by 2n-3 distances: its n
edges plus a fan of n-3 diagonals from corner 1. A line gets one distance per segment, a circle
its radius. Fitting moves the corners as little as possible so that the shape's own distances
match the tape: a least-squares fit, with a feather-light pull toward where the corners were
drawn so the result is not shifted, turned or mirrored from what is on the map.

Pure numpy; positions are projected to local metres, so none of this touches the database.
"""

from dataclasses import dataclass

import numpy as np

from . import mapping_geo as geo

RECHECK_M = 0.15  # after fitting, a distance still this far out was probably mis-measured
MIN_VALUE_M = 0.01
MAX_VALUE_M = 1000.0
PRIOR_WEIGHT = 1e-3


@dataclass(frozen=True)
class Spec:
    kind: str  # edge | diagonal | radius | custom
    a: int  # corner index (0-based)
    b: int


def corners(geometry: dict) -> list[tuple[float, float]]:
    """The (lon, lat) corners of a feature, without a polygon's repeated closing point."""
    kind, coords = geometry["type"], geometry["coordinates"]
    if kind == "Polygon":
        return [tuple(c[:2]) for c in coords[0][:-1]]
    if kind == "LineString":
        return [tuple(c[:2]) for c in coords]
    return [tuple(coords[:2])]


def expected(geometry_type: str, n: int, radius_m: float | None) -> list[Spec]:
    """The distances to measure for a shape with ``n`` corners."""
    if geometry_type == "Polygon" and n >= 3:
        edges = [Spec("edge", i, (i + 1) % n) for i in range(n)]
        diagonals = [Spec("diagonal", 0, k) for k in range(2, n - 1)]
        return edges + diagonals
    if geometry_type == "LineString" and n >= 2:
        return [Spec("edge", i, i + 1) for i in range(n - 1)]
    if geometry_type == "Point" and radius_m:
        return [Spec("radius", 0, 0)]
    return []


def to_metres(points: list[tuple[float, float]], origin: tuple[float, float]) -> np.ndarray:
    lat_m, lng_m = geo.metres_per_degree(origin[1])
    return np.array([((lng - origin[0]) * lng_m, (lat - origin[1]) * lat_m) for lng, lat in points])


def from_metres(xy: np.ndarray, origin: tuple[float, float]) -> list[tuple[float, float]]:
    lat_m, lng_m = geo.metres_per_degree(origin[1])
    return [(origin[0] + x / lng_m, origin[1] + y / lat_m) for x, y in xy]


def centre(points: list[tuple[float, float]]) -> tuple[float, float]:
    arr = np.array(points)
    return float(arr[:, 0].mean()), float(arr[:, 1].mean())


def drawn_length(xy: np.ndarray, spec: Spec, radius_m: float | None) -> float:
    if spec.kind == "radius":
        return float(radius_m or 0.0)
    return float(np.linalg.norm(xy[spec.a] - xy[spec.b]))


@dataclass
class Fit:
    xy: np.ndarray  # corrected corners, local metres
    before: np.ndarray  # distance error per constraint, drawn shape
    after: np.ndarray  # distance error per constraint, corrected shape
    missing: int  # measurements still needed to fix the shape (0 if fixed)
    recheck: list[int]  # indexes of constraints still out after fitting


def _distances(xy: np.ndarray, pairs: np.ndarray) -> np.ndarray:
    return np.linalg.norm(xy[pairs[:, 0]] - xy[pairs[:, 1]], axis=1)


def _jacobian(xy: np.ndarray, pairs: np.ndarray) -> np.ndarray:
    n = len(xy)
    jac = np.zeros((len(pairs), 2 * n))
    for row, (i, j) in enumerate(pairs):
        delta = xy[i] - xy[j]
        length = np.linalg.norm(delta)
        unit = delta / length if length > 1e-9 else np.array([1.0, 0.0])
        jac[row, 2 * i : 2 * i + 2] += unit
        jac[row, 2 * j : 2 * j + 2] -= unit
    return jac


def fit_shape(xy: np.ndarray, constraints: list[tuple[int, int, float]], closed: bool) -> Fit:
    """Move the corners so the measured distances hold, changing the drawn shape as little as
    possible. ``constraints`` are (corner a, corner b, metres)."""
    pairs = np.array([(a, b) for a, b, _ in constraints], dtype=int)
    wanted = np.array([d for _, _, d in constraints], dtype=float)
    start = xy.astype(float).copy()
    before = _distances(start, pairs) - wanted

    # How many measurements are still needed: a fixed shape has 2n-3 independent distances.
    rank = int(np.linalg.matrix_rank(_jacobian(start, pairs), tol=1e-6))
    needed = 2 * len(xy) - 3 if closed else 0
    missing = max(0, needed - rank) if closed else 0

    pts = start.copy()
    damping = 1e-3
    flat0 = start.ravel()

    def residuals(p: np.ndarray) -> np.ndarray:
        return np.concatenate([_distances(p, pairs) - wanted, PRIOR_WEIGHT * (p.ravel() - flat0)])

    cost = float(np.sum(residuals(pts) ** 2))
    for _ in range(100):
        jac = np.vstack([_jacobian(pts, pairs), PRIOR_WEIGHT * np.eye(pts.size)])
        res = residuals(pts)
        step = np.linalg.solve(jac.T @ jac + damping * np.eye(pts.size), -jac.T @ res)
        trial = pts + step.reshape(pts.shape)
        trial_cost = float(np.sum(residuals(trial) ** 2))
        if trial_cost < cost:
            improved = cost - trial_cost
            pts, cost, damping = trial, trial_cost, max(damping / 3, 1e-9)
            if improved < 1e-14:
                break
        else:
            damping *= 4
            if damping > 1e9:
                break
    after = _distances(pts, pairs) - wanted
    recheck = [i for i, r in enumerate(after) if abs(r) > RECHECK_M]
    return Fit(pts, before, after, missing, recheck)
