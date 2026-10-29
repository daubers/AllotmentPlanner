"""Using a boundary you already know (from a GPX trace) to help place what the photos found. Pure.

Two uses, both in the reconstruction's own metres (east, north) around its reference point:

* **Objects.** The detector also sees neighbours' sheds and trees. An object belongs to the plot if
  its centre is inside the boundary (with a little slack, because a GPS trace wanders by a metre
  or two) or at least half of its footprint is. The rest are left out, and said so.
* **Cameras.** The photos were taken in and around the plot, so almost all camera positions should
  be inside the boundary. If most are not, the trace and the photos' GPS disagree about where the
  plot is, and every placement is suspect: that is reported, with how far off, instead of hidden.
"""

import math
from dataclasses import dataclass
from typing import Protocol

from shapely.geometry import Point, Polygon, shape

from . import mapping_geo as geo
from .gpx import MAX_AREA_M2, MIN_AREA_M2
from .plantings import area_m2

OBJECT_SLACK_M = 1.5  # a centre this far outside the trace still counts as inside
CAMERA_SLACK_M = 3.0  # people photograph the plot from just outside it too
MIN_FOOTPRINT_INSIDE = 0.5
CAMERAS_INSIDE_OK = 0.6


class Placed(Protocol):
    x: float
    y: float
    width: float
    depth: float


def boundary_problem(geometry) -> str | None:
    """Why ``geometry`` cannot be a plot boundary; None if it can."""
    if not isinstance(geometry, dict) or geometry.get("type") != "Polygon":
        return "The boundary must be a GeoJSON Polygon"
    try:
        poly = shape(geometry)
    except (ValueError, TypeError, KeyError, AttributeError, IndexError):
        return "The boundary is not a valid polygon"
    if poly.is_empty or not poly.is_valid:
        return "The boundary is empty or crosses itself"
    minx, miny, maxx, maxy = poly.bounds
    if not (-180 <= minx and maxx <= 180 and -90 <= miny and maxy <= 90):
        return "The boundary's coordinates must be [longitude, latitude]"
    size = area_m2(poly)
    if size < MIN_AREA_M2:
        return "The boundary is too small to be a plot"
    if size > MAX_AREA_M2:
        return "The boundary is too large to be a plot"
    return None


def to_enu(boundary: dict, reference: tuple[float, float]) -> Polygon:
    """A GeoJSON polygon (lon/lat) in metres east and north of ``reference`` (lat, lon)."""
    lat0, lon0 = reference
    lat_m, lon_m = geo.metres_per_degree(lat0)
    ring = boundary["coordinates"][0]
    return Polygon([((lon - lon0) * lon_m, (lat - lat0) * lat_m) for lon, lat in ring])


def belongs(poly: Polygon, obj: Placed) -> bool:
    """Whether an object is part of the plot rather than next door."""
    centre = Point(obj.x, obj.y)
    if poly.buffer(OBJECT_SLACK_M).contains(centre):
        return True
    radius = max(obj.width, obj.depth) / 2
    if radius <= 0:
        return False
    footprint = centre.buffer(radius)
    return poly.intersection(footprint).area / footprint.area >= MIN_FOOTPRINT_INSIDE


def keep_inside(poly: Polygon, objects: list) -> tuple[list, list]:
    """(kept, dropped): the objects that belong to the plot, and those that are outside it."""
    kept = [o for o in objects if belongs(poly, o)]
    return kept, [o for o in objects if o not in kept]


@dataclass
class CameraCheck:
    inside: int
    total: int
    offset_m: float | None  # how far the cameras' centre is from the plot, when most are outside

    @property
    def fraction(self) -> float:
        return self.inside / self.total if self.total else 1.0

    @property
    def agrees(self) -> bool:
        return self.total == 0 or self.fraction >= CAMERAS_INSIDE_OK

    def message(self) -> str | None:
        """What to tell the person, or None when the photos and the trace agree."""
        if self.agrees:
            return None
        return (
            f"Only {self.inside} of {self.total} photo positions are inside the GPX boundary"
            + (f" (about {self.offset_m:.0f} m off)" if self.offset_m is not None else "")
            + ". The trace or the photos' GPS is out of place, so object positions may be too"
        )


def check_cameras(poly: Polygon, cameras: list[tuple[float, float]]) -> CameraCheck:
    """How many camera positions fall inside the boundary (with some slack)."""
    padded = poly.buffer(CAMERA_SLACK_M)
    inside = sum(1 for x, y in cameras if padded.contains(Point(x, y)))
    offset = None
    if cameras and inside / len(cameras) < CAMERAS_INSIDE_OK:
        cx = sum(x for x, _ in cameras) / len(cameras)
        cy = sum(y for _, y in cameras) / len(cameras)
        offset = poly.distance(Point(cx, cy)) if not poly.contains(Point(cx, cy)) else 0.0
        if (
            offset == 0.0
        ):  # the centre is inside but the cameras are spread far beyond: use the typical miss
            offset = math.dist((cx, cy), (poly.centroid.x, poly.centroid.y))
    return CameraCheck(inside, len(cameras), offset)
