"""From segmentation masks in photos to objects on the ground.

A detector finds things in each photo (a mask per thing). OpenSfM gives every photo's camera pose,
so a mask can be turned into a place on the ground. One photo can't give an object's depth, so:

* the object is assumed to stand on the ground, and its **contact line** (the lowest mask pixel in
  each column) is cast onto the ground plane. That gives where it is and how wide it is;
* the depth (how far back it extends) is a guess, unless several photos see it from different
  sides, in which case the guesses average out around the true centre;
* detections of the same kind that land in about the same place are merged into one object.

Pure numpy (plus shapely for outlines), so it is tested against a synthetic scene with known
cylinders and boxes, with no model involved.
"""

import math
from dataclasses import dataclass, field

import numpy as np

from .detection_labels import width_is_plausible
from .mapping_geo import Shot, ground_hits

MAX_RANGE_M = 25.0  # ignore anything further away: its position is too uncertain to be useful
MIN_CONTACT_POINTS = 4
RECT_DEPTH_RATIO = 0.7  # box-like things are assumed this deep relative to their width
MIN_SIZE_M = 0.15


@dataclass(frozen=True)
class Footprint:
    """One object as seen from one photo, on the ground (ENU metres)."""

    x: float
    y: float
    width: float  # across the line of sight
    depth: float  # along it (a guess)
    angle: float  # direction of the width axis, radians from east
    distance: float  # camera to the contact line
    score: float  # detector confidence


@dataclass
class Observation:
    label: str  # e.g. "water butt"
    kind: str  # FeatureKind value
    shape: str  # circle | rect
    footprint: Footprint
    shot: str
    outline: list[list[float]] | None = None  # see silhouette()


@dataclass
class FusedObject:
    label: str
    kind: str
    shape: str
    x: float
    y: float
    width: float
    depth: float
    angle: float
    confidence: float
    views: int
    members: list[Observation] = field(default_factory=list, repr=False)


def contact_points(mask: np.ndarray, columns: int = 40) -> np.ndarray | None:
    """Pixels (x, y) along the bottom edge of a boolean mask, or None if the object's base is not
    in the picture (its mask runs off the bottom of the frame)."""
    h, _ = mask.shape
    cols = np.flatnonzero(mask.any(axis=0))
    if cols.size == 0:
        return None
    # Sample across the object's own width: a narrow object still needs enough points.
    xs = np.unique(np.linspace(cols[0], cols[-1], min(columns, cols.size)).astype(int))
    pts = []
    touching = 0
    for x in xs:
        rows = np.flatnonzero(mask[:, x])
        if rows.size == 0:
            continue
        bottom = rows[-1]
        if bottom >= h - 2:
            touching += 1
            continue
        pts.append((x + 0.5, bottom + 0.5))
    if len(pts) < MIN_CONTACT_POINTS or touching > len(pts):
        return None
    return np.array(pts, dtype=float)


def silhouette(mask: np.ndarray, rows: int = 12) -> list[list[float]] | None:
    """A rough outline of a boolean mask as [x, y] points scaled to 0..1 of the mask's width and
    height, so it can be drawn over the same picture at any size. The left and right edge of the
    mask at a handful of heights, joined into one ring: enough to show which thing was found."""
    h, w = mask.shape
    ys = np.flatnonzero(mask.any(axis=1))
    if ys.size == 0:
        return None
    picks = np.unique(np.linspace(ys[0], ys[-1], min(rows, ys.size)).astype(int))
    left, right = [], []
    for y in picks:
        xs = np.flatnonzero(mask[y])
        if xs.size:
            left.append((xs[0], y))
            right.append((xs[-1] + 1, y))
    ring = left + right[::-1]
    if len(ring) < 3:
        return None
    return [[round(x / w, 4), round(y / h, 4)] for x, y in ring]


def footprint_from_mask(
    shot: Shot,
    plane: tuple[float, float, float],
    mask: np.ndarray,
    score: float,
    shape: str,
    scale: float = 1.0,
    max_range: float = MAX_RANGE_M,
) -> Footprint | None:
    """Where on the ground an object is, from one mask. ``scale`` converts mask pixels to the
    camera's pixels (the detector may have worked on a smaller copy of the photo)."""
    pixels = contact_points(mask)
    if pixels is None:
        return None
    return footprint_from_pixels(shot, plane, pixels * scale, score, shape, max_range)


def why_no_footprint(
    shot: Shot,
    plane: tuple[float, float, float],
    pixels: np.ndarray,
    max_range: float = MAX_RANGE_M,
) -> str:
    """Why ``footprint_from_pixels`` gave nothing, in a word, so a run that finds nothing can say
    which way it failed: "no ground" (the rays miss the ground plane or land past ``max_range``),
    "too close" (under 0.3 m from the camera), or "other"."""
    hits = ground_hits(shot, plane, pixels, max_range)
    ok = ~np.isnan(hits).any(axis=1)
    if ok.sum() < MIN_CONTACT_POINTS:
        return "no ground"
    p = hits[ok][:, :2]
    if float(np.linalg.norm(np.median(p, axis=0) - shot.centre[:2])) < 0.3:
        return "too close"
    return "other"


def footprint_from_pixels(
    shot: Shot,
    plane: tuple[float, float, float],
    pixels: np.ndarray,
    score: float,
    shape: str,
    max_range: float = MAX_RANGE_M,
) -> Footprint | None:
    """The same from the contact pixels (camera pixels) alone, so a mask need not be kept."""
    hits = ground_hits(shot, plane, pixels, max_range)
    ok = ~np.isnan(hits).any(axis=1)
    if ok.sum() < MIN_CONTACT_POINTS:
        return None
    p = hits[ok][:, :2]
    cam = shot.centre[:2]
    to_obj = np.median(p, axis=0) - cam
    distance = float(np.linalg.norm(to_obj))
    if distance < 0.3:
        return None
    ray = to_obj / distance
    lateral = np.array([-ray[1], ray[0]])
    across = (p - cam) @ lateral
    along = (p - cam) @ ray
    width = float((np.percentile(across, 95) - np.percentile(across, 5)) / 0.9)
    width = max(width, MIN_SIZE_M)
    depth = width if shape == "circle" else max(RECT_DEPTH_RATIO * width, MIN_SIZE_M)
    near = float(np.median(along))
    centre_across = float((np.percentile(across, 95) + np.percentile(across, 5)) / 2)
    centre = cam + ray * (near + depth / 2) + lateral * centre_across
    # The contact line's direction is a box's orientation (needs well spread points).
    angle = math.atan2(lateral[1], lateral[0])
    if shape == "rect" and len(p) >= 6:
        centred = p - p.mean(axis=0)
        _, _, vt = np.linalg.svd(centred, full_matrices=False)
        if np.ptp(centred @ vt[0]) > 2 * np.ptp(centred @ vt[1]):  # clearly a line, not a blob
            angle = math.atan2(vt[0][1], vt[0][0])
    return Footprint(
        float(centre[0]), float(centre[1]), width, depth, angle, distance, float(score)
    )


def scaled(f: Footprint, factor: float) -> Footprint:
    """The footprint with every length multiplied by ``factor`` (positions about the origin)."""
    return Footprint(
        f.x * factor,
        f.y * factor,
        f.width * factor,
        f.depth * factor,
        f.angle,
        f.distance * factor,
        f.score,
    )


def contact_ground_points(
    shot: Shot,
    plane: tuple[float, float, float],
    mask: np.ndarray,
    scale: float = 1.0,
    max_range: float = MAX_RANGE_M,
    limit: int = 12,
) -> np.ndarray:
    """Ground positions (east, north) along the foot of a mask, at most ``limit`` of them spread
    along it: used for fences and posts, where it is the line on the ground that matters."""
    pixels = contact_points(mask)
    if pixels is None:
        return np.zeros((0, 2))
    return ground_points_from_pixels(shot, plane, pixels * scale, max_range, limit)


def ground_points_from_pixels(
    shot: Shot,
    plane: tuple[float, float, float],
    pixels: np.ndarray,
    max_range: float = MAX_RANGE_M,
    limit: int = 12,
) -> np.ndarray:
    hits = ground_hits(shot, plane, pixels, max_range)
    ok = hits[~np.isnan(hits).any(axis=1)][:, :2]
    if len(ok) > limit:
        ok = ok[np.linspace(0, len(ok) - 1, limit).astype(int)]
    return ok


def _same_object(a: FusedObject, o: Observation) -> bool:
    f = o.footprint
    size = max(a.width, f.width)
    close = math.hypot(a.x - f.x, a.y - f.y) < max(0.6, 0.6 * size)
    ratio = f.width / a.width if a.width else 1
    return close and 0.4 < ratio < 2.5


def _weight(f: Footprint) -> float:
    return f.score / (1 + f.distance / 8)


def fuse(observations: list[Observation], min_views: int = 1) -> list[FusedObject]:
    """Merge detections of the same kind of thing that land in the same place. Nearer, more
    confident observations count for more (position error grows with distance)."""
    groups: list[FusedObject] = []
    for o in sorted(observations, key=lambda o: -_weight(o.footprint)):
        match = next((g for g in groups if g.label == o.label and _same_object(g, o)), None)
        if match is None:
            f = o.footprint
            groups.append(
                FusedObject(
                    o.label, o.kind, o.shape, f.x, f.y, f.width, f.depth, f.angle, 0.0, 0, [o]
                )
            )
        else:
            match.members.append(o)
            _recentre(match)
    result = []
    for g in groups:
        g.views = len({m.shot for m in g.members})
        if g.views < min_views:
            continue
        mean_score = float(np.mean([m.footprint.score for m in g.members]))
        g.confidence = round(mean_score * min(1.0, 0.5 + g.views / 6), 3)
        result.append(g)
    return sorted(result, key=lambda g: -g.confidence)


def _recentre(g: FusedObject) -> None:
    w = np.array([_weight(m.footprint) for m in g.members])
    f = [m.footprint for m in g.members]
    g.x = float(np.average([x.x for x in f], weights=w))
    g.y = float(np.average([x.y for x in f], weights=w))
    g.width = float(np.median([x.width for x in f]))
    g.depth = float(np.median([x.depth for x in f]))
    # Mean orientation, angles doubled: a rectangle looks the same turned half a circle.
    a = np.array([x.angle for x in f])
    g.angle = float(
        np.arctan2(np.average(np.sin(2 * a), weights=w), np.average(np.cos(2 * a), weights=w)) / 2
    )


def outline(g: FusedObject, steps: int = 24) -> list[tuple[float, float]]:
    """The object's outline as (east, north) ENU points: a circle or a rotated rectangle."""
    if g.shape == "circle":
        r = max(g.width, g.depth) / 2
        return [
            (g.x + r * math.cos(t), g.y + r * math.sin(t))
            for t in np.linspace(0, 2 * math.pi, steps, endpoint=False)
        ]
    c, s = math.cos(g.angle), math.sin(g.angle)
    corners = [
        (-g.width / 2, -g.depth / 2),
        (g.width / 2, -g.depth / 2),
        (g.width / 2, g.depth / 2),
        (-g.width / 2, g.depth / 2),
    ]
    return [(g.x + dx * c - dy * s, g.y + dx * s + dy * c) for dx, dy in corners]


def worth_keeping(g: FusedObject, solo_confidence: float = 0.45) -> bool:
    """Drop what is probably noise: a size the type can't have, or something only one photo
    showed unless the detector was fairly sure of it."""
    if not width_is_plausible(g.label, max(g.width, g.depth if g.shape == "circle" else 0)):
        return False
    return g.views >= 2 or g.confidence >= solo_confidence
