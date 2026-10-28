"""Finding the ground's height below the cameras from the detections themselves.

The sparse point cloud OpenSfM returns for a hand-held outdoor scene is mostly far-off things at
about camera height (the horizon, trees, other plots) with almost nothing on the grass near the
camera, so fitting the ground to it puts the ground in the wrong place and the scale with it.

A better clue: an object seen from several photos must land in the *same place* on the ground, and
it only does if the ground plane is at the right height below the cameras. So try a range of
heights, put every detection on the ground at each, and keep the height at which detections from
different photos agree best. Together with how high the camera was really held, that gives the
scale.
"""

from dataclasses import dataclass

import numpy as np

from . import detection_geo as dg
from .mapping_geo import Shot

MAX_PLATEAU = 8  # candidates (about 12% apart) allowed within 60% of the best agreement


@dataclass(frozen=True)
class RawDetection:
    """What is kept of a detection once its mask is thrown away."""

    shot: str
    label: str
    kind: str
    shape: str
    score: float
    pixels: np.ndarray  # (N, 2) camera pixels along the foot of the mask
    role: str = "object"  # "object", "post" or "fence" (see detection_labels)


@dataclass(frozen=True)
class Calibration:
    height_units: float  # camera height above the ground in the reconstruction's own units
    agreement: float  # share of detections that matched one from another photo (0 to 1)
    objects: int  # detections the figure rests on


def level_plane(shots: list[Shot], height: float) -> tuple[float, float, float]:
    """A level ground plane ``height`` below the middle camera height."""
    return (0.0, 0.0, float(np.median([s.centre[2] for s in shots])) - height)


def agreement(observations: list[dg.Observation]) -> float:
    """Share of observations that were merged with one from a different photo."""
    if not observations:
        return 0.0
    merged = dg.fuse(observations)
    in_groups = sum(len(g.members) for g in merged if g.views >= 2)
    return in_groups / len(observations)


def calibrate_height(
    shots: list[Shot],
    raws: list[RawDetection],
    stated_height: float,
    candidates: np.ndarray | None = None,
    max_range: float = dg.MAX_RANGE_M,
    min_objects: int = 12,
) -> Calibration | None:
    """The camera height (in the reconstruction's units) at which detections agree best.

    Each candidate height implies a scale (``stated_height`` / height), and distances are compared
    in metres at that scale, so the same 0.6 m "same object" rule applies throughout. The best
    candidate must be a sharp peak: a flat curve means the data can't decide."""
    by_name = {s.name: s for s in shots}
    raws = [r for r in raws if r.shot in by_name and len(r.pixels) >= dg.MIN_CONTACT_POINTS]
    if len(raws) < min_objects:
        return None
    if candidates is None:
        candidates = np.geomspace(
            0.15, 12.0, 40
        )  # a wide range: scale can be wrong several times over
    scores = []
    for height in candidates:
        plane = level_plane(shots, float(height))
        factor = stated_height / float(height)
        obs = []
        for r in raws:
            fp = dg.footprint_from_pixels(
                by_name[r.shot], plane, r.pixels, r.score, r.shape, max_range=max_range / factor
            )
            if fp:
                obs.append(dg.Observation(r.label, r.kind, r.shape, dg.scaled(fp, factor), r.shot))
        scores.append((agreement(obs), len(obs)))
    values = np.array([s[0] for s in scores])
    best = int(np.argmax(values))
    if values[best] < 0.35:
        return None  # hardly anything matched across photos
    # A real answer is a needle: agreement collapses within a few tens of percent either side of the
    # true height. Random detections that happen to land near each other agree over a wide plateau.
    plateau = int((values >= 0.6 * values[best]).sum())
    if plateau > MAX_PLATEAU:
        return None
    return Calibration(float(candidates[best]), float(values[best]), scores[best][1])
