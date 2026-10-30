"""GeoJSON <-> MapFeature conversion and validation."""

from geoalchemy2.shape import from_shape, to_shape
from marshmallow import ValidationError
from shapely.geometry import mapping, shape

from .models import FeatureKind, MapFeature

ALLOWED_GEOMETRIES = {"Point", "LineString", "Polygon"}


def parse_geometry(geometry: dict):
    """Validate a GeoJSON geometry and return a PostGIS element (SRID 4326)."""
    if not isinstance(geometry, dict) or geometry.get("type") not in ALLOWED_GEOMETRIES:
        raise ValidationError(f"geometry.type must be one of {sorted(ALLOWED_GEOMETRIES)}")
    try:
        geom = shape(geometry)
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise ValidationError(f"Invalid geometry: {exc}") from exc
    if geom.is_empty or not geom.is_valid:
        raise ValidationError("Geometry is empty or invalid (e.g. self-intersecting polygon)")
    minx, miny, maxx, maxy = geom.bounds
    if not (-180 <= minx and maxx <= 180 and -90 <= miny and maxy <= 90):
        raise ValidationError("Coordinates must be [longitude, latitude] within WGS84 bounds")
    return from_shape(geom, srid=4326)


def check_feature_rules(kind: str, geometry_type: str, radius_m: float | None) -> None:
    if kind not in {k.value for k in FeatureKind}:
        raise ValidationError(f"kind must be one of {[k.value for k in FeatureKind]}")
    if radius_m is not None and geometry_type != "Point":
        raise ValidationError("radius_m is only valid on Point geometries (circles)")


def feature_to_geojson(feature: MapFeature) -> dict:
    return {
        "type": "Feature",
        "id": feature.id,
        "geometry": mapping(to_shape(feature.geometry)),
        "properties": {
            "name": feature.name,
            "kind": feature.kind,
            "radius_m": feature.radius_m,
            "style": feature.style or {},
            "locked": bool(feature.locked),
            "z": feature.z or 0,
        },
    }
