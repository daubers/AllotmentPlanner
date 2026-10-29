"""Reads a GPX file and turns a walk round the plot's edge into a boundary polygon. Pure.

A GPX file is what a phone or watch records when you walk the fence line. Only positions matter
here (time and elevation are ignored). A recorded walk is noisy, may be paused into several
segments, and rarely ends exactly where it started, so the trace is joined up, simplified, and
closed if its ends are close enough: a walk that stops 60 m short of its start is probably not a
plot at all, and is refused with that reason rather than guessed at.
"""

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from shapely.geometry import Polygon
from shapely.geometry.polygon import orient
from shapely.validation import make_valid

MAX_BYTES = 5 * 1024 * 1024
MIN_POINTS = 4
MIN_AREA_M2 = 4.0
MAX_AREA_M2 = 500_000.0  # half a square kilometre: far beyond any allotment
CLOSE_UP_TO_M = 5.0  # ends this close are simply joined
MAX_GAP_M = 25.0  # a bigger gap is "not back where it started"
SIMPLIFY_M = 0.4  # GPS wobble; also keeps the polygon small
M_PER_DEG_LAT = 111_320.0


class GpxError(ValueError):
    """The file cannot be used, with a reason fit to show the person."""


@dataclass
class Trace:
    points: list[tuple[float, float]]  # (lon, lat), in walking order
    kind: str  # track | route | waypoints
    segments: int
    name: str | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class Outline:
    polygon: Polygon  # lon/lat, counter-clockwise, closed
    area_m2: float
    perimeter_m: float
    gap_m: float  # between the walk's start and end, before they were joined
    points_in: int
    points_out: int
    warnings: list[str] = field(default_factory=list)


def _local(tag: str) -> str:
    """An element's name without its namespace (GPX 1.0 and 1.1 use different ones)."""
    return tag.rsplit("}", 1)[-1]


def _points(parent: ET.Element, name: str) -> list[tuple[float, float]]:
    out = []
    for el in parent.iter():
        if _local(el.tag) != name:
            continue
        try:
            lat, lon = float(el.attrib["lat"]), float(el.attrib["lon"])
        except (KeyError, ValueError):
            continue
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            out.append((lon, lat))
    return out


def parse_gpx(data: bytes | str) -> Trace:
    """The walk in a GPX file: the longest track (segments joined), else a route, else waypoints."""
    raw = data.encode() if isinstance(data, str) else data
    if len(raw) > MAX_BYTES:
        raise GpxError("That file is too big for a GPX trace (over 5 MB)")
    if re.search(rb"<!\s*(DOCTYPE|ENTITY)", raw, re.I):
        raise GpxError("That is not a plain GPX file")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise GpxError("That is not a readable GPX file") from exc
    if _local(root.tag) != "gpx":
        raise GpxError("That is not a GPX file (it should start with <gpx>)")

    warnings: list[str] = []
    tracks = []
    for trk in (el for el in root if _local(el.tag) == "trk"):
        segs = [s for s in trk if _local(s.tag) == "trkseg"]
        pts = [p for s in segs for p in _points(s, "trkpt")]
        name = next((c.text for c in trk if _local(c.tag) == "name" and c.text), None)
        tracks.append((pts, max(len(segs), 1), name))
    tracks = [t for t in tracks if t[0]]
    if tracks:
        pts, segments, name = max(tracks, key=lambda t: len(t[0]))
        if len(tracks) > 1:
            warnings.append(f"The file has {len(tracks)} tracks; the longest was used")
        kind = "track"
    else:
        routes = [_points(r, "rtept") for r in root if _local(r.tag) == "rte"]
        routes = [r for r in routes if r]
        if routes:
            pts, segments, name, kind = max(routes, key=len), 1, None, "route"
        else:
            pts, segments, name, kind = _points(root, "wpt"), 1, None, "waypoints"
    if not pts:
        raise GpxError("The file has no track, route or waypoints")
    deduped = [p for i, p in enumerate(pts) if i == 0 or p != pts[i - 1]]
    if len(deduped) < MIN_POINTS:
        raise GpxError(
            f"The trace has only {len(deduped)} distinct points: too few to outline a plot"
        )
    return Trace(deduped, kind, segments, name, warnings)


def _to_metres(points, lon0: float, lat0: float) -> list[tuple[float, float]]:
    k = M_PER_DEG_LAT * math.cos(math.radians(lat0))
    return [((lon - lon0) * k, (lat - lat0) * M_PER_DEG_LAT) for lon, lat in points]


def _to_lonlat(points, lon0: float, lat0: float) -> list[tuple[float, float]]:
    k = M_PER_DEG_LAT * math.cos(math.radians(lat0))
    return [(lon0 + x / k, lat0 + y / M_PER_DEG_LAT) for x, y in points]


def outline_from_trace(
    trace: Trace, simplify_m: float = SIMPLIFY_M, max_gap_m: float = MAX_GAP_M
) -> Outline:
    """The polygon the walk encloses, in lon/lat. Raises GpxError if there is no sensible plot."""
    lons = [p[0] for p in trace.points]
    lats = [p[1] for p in trace.points]
    lon0, lat0 = sum(lons) / len(lons), sum(lats) / len(lats)
    xy = _to_metres(trace.points, lon0, lat0)
    gap = math.dist(xy[0], xy[-1])
    warnings = list(trace.warnings)
    if gap > max_gap_m:
        raise GpxError(
            f"The walk stops {gap:.0f} m from where it started. Walk right round the plot and "
            "finish at the start to close it"
        )
    if gap > CLOSE_UP_TO_M:
        warnings.append(f"The ends of the walk were {gap:.0f} m apart and have been joined up")

    poly = Polygon(xy)
    if not poly.is_valid:
        fixed = make_valid(poly)
        parts = [g for g in getattr(fixed, "geoms", [fixed]) if isinstance(g, Polygon)]
        if not parts:
            raise GpxError("The trace does not enclose an area")
        poly = max(parts, key=lambda g: g.area)
        warnings.append("The walk crosses itself; the largest loop was used")
    simple = poly.simplify(simplify_m, preserve_topology=True)
    if isinstance(simple, Polygon) and not simple.is_empty and len(simple.exterior.coords) >= 4:
        poly = simple
    poly = orient(poly, 1.0)
    if poly.area < MIN_AREA_M2:
        raise GpxError(f"The trace encloses only {poly.area:.1f} m²: too small to be a plot")
    if poly.area > MAX_AREA_M2:
        raise GpxError("The trace encloses more than half a square kilometre: not a plot")
    if len(trace.points) < 12:
        warnings.append("Few points: a trace recorded every second follows the edge more closely")

    ring = _to_lonlat(list(poly.exterior.coords), lon0, lat0)
    return Outline(
        polygon=Polygon(ring),
        area_m2=round(poly.area, 1),
        perimeter_m=round(poly.length, 1),
        gap_m=round(gap, 1),
        points_in=len(trace.points),
        points_out=len(ring) - 1,
        warnings=warnings,
    )
