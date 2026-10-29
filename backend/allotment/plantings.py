"""What is growing where: the rules for plantings in a bed. Pure: GeoJSON and plain values in.

A planting is a drawn region inside a bed. Regions may overlap (inter-planting, a quick crop between
slow ones), so an overlap is a warning, not an error; a region outside its bed is an error.
Areas and distances use a flat approximation around the shape (metres per degree of latitude and
longitude at that latitude), which is exact enough at the scale of an allotment.
"""

import math

from shapely.affinity import scale, translate
from shapely.geometry import Polygon, shape

METHODS = ("direct_sow", "transplant")
STATUSES = ("sown", "growing", "harvesting", "finished", "failed")
GROWING = ("sown", "growing", "harvesting")  # still occupying the ground: overlaps matter
M_PER_DEG_LAT = 111_320.0
EDGE_TOLERANCE_M = 0.3  # a corner clicked a little over the edge of the bed is forgiven
MIN_AREA_M2 = 0.01
MIN_OVERLAP_M2 = 0.02


def _metres_per_degree_lon(lat: float) -> float:
    return M_PER_DEG_LAT * math.cos(math.radians(lat))


def to_polygon(geometry: dict) -> Polygon | None:
    """The polygon for a GeoJSON Polygon, or None if it is anything else or empty."""
    if not isinstance(geometry, dict) or geometry.get("type") != "Polygon":
        return None
    try:
        poly = shape(geometry)
    except (ValueError, TypeError, KeyError, AttributeError):
        return None
    return poly if isinstance(poly, Polygon) and not poly.is_empty else None


def _in_metres(poly: Polygon, origin: tuple[float, float]) -> Polygon:
    """The polygon in flat metres east and north of ``origin`` (lon, lat)."""
    lon0, lat0 = origin
    per_lon = _metres_per_degree_lon(lat0)
    moved = translate(poly, xoff=-lon0, yoff=-lat0)
    return scale(moved, xfact=per_lon, yfact=M_PER_DEG_LAT, origin=(0, 0))


def _origin(poly: Polygon) -> tuple[float, float]:
    c = poly.centroid
    return c.x, c.y


def area_m2(poly: Polygon) -> float:
    return _in_metres(poly, _origin(poly)).area


def region_problem(region: dict, bed: dict) -> str | None:
    """Why ``region`` cannot be planted in ``bed`` (both GeoJSON); None if it can."""
    poly, bed_poly = to_polygon(region), to_polygon(bed)
    if bed_poly is None:
        return "Plantings can only go in a bed drawn as an area"
    if poly is None:
        return "The planting region must be a polygon"
    if not poly.is_valid:
        return "The planting region crosses itself"
    if area_m2(poly) < MIN_AREA_M2:
        return "The planting region is too small"
    origin = _origin(bed_poly)
    if not _in_metres(bed_poly, origin).buffer(EDGE_TOLERANCE_M).contains(_in_metres(poly, origin)):
        return "The planting region goes outside the bed"
    return None


def overlaps(region: dict, others: list[tuple[int, str, dict]]) -> list[tuple[int, str, float]]:
    """Which of ``others`` (id, label, region) the new region overlaps, and by how many m2."""
    poly = to_polygon(region)
    if poly is None:
        return []
    origin = _origin(poly)
    flat = _in_metres(poly, origin)
    found = []
    for other_id, label, other in others:
        other_poly = to_polygon(other)
        if other_poly is None or not other_poly.is_valid:
            continue
        shared = flat.intersection(_in_metres(other_poly, origin)).area
        if shared >= MIN_OVERLAP_M2:
            found.append((other_id, label, round(shared, 2)))
    return found


def overlap_warning(label: str, shared_m2: float) -> str:
    return f"Overlaps {label} by {shared_m2:g} m²"


class PlantOutError(ValueError):
    """The chosen cells cannot be planted out."""


def plant_out_groups(cells: list[dict]) -> dict[int | None, list[dict]]:
    """Group the chosen tray cells by packet, one planting each; refuse cells that cannot go out.

    Each cell is a dict with row, col, status, packet_id. Only sown or germinated cells can be
    planted out: an empty cell has nothing in it, a failed one did not come up, and a planted-out
    one has already gone.
    """
    if not cells:
        raise PlantOutError("Choose at least one cell")
    groups: dict[int | None, list[dict]] = {}
    for cell in cells:
        where = f"Row {cell['row'] + 1}, column {cell['col'] + 1}"
        status = cell.get("status")
        if status is None:
            raise PlantOutError(f"{where}: nothing is sown there")
        if status == "planted_out":
            raise PlantOutError(f"{where}: already planted out")
        if status == "failed":
            raise PlantOutError(f"{where}: did not come up")
        groups.setdefault(cell.get("packet_id"), []).append(cell)
    return groups
