from flask.views import MethodView
from flask_smorest import Blueprint, abort
from marshmallow import ValidationError

from .. import events
from ..extensions import db
from ..geojson import check_feature_rules, feature_to_geojson, parse_geometry
from ..models import FeatureKind, MapFeature, Role
from ..schemas import (
    FeatureCollectionInSchema,
    FeatureCollectionSchema,
    FeatureInSchema,
    FeaturePatchSchema,
    FeatureSchema,
)
from ..security import require_role

blp = Blueprint(
    "features",
    __name__,
    url_prefix="/api/v1/allotments/<int:allotment_id>/features",
    description="Map features (GeoJSON)",
)

PROPERTY_KEYS = {"name", "kind", "radius_m", "style", "locked", "z"}


def _reject(message: str):
    """Discard any half-applied changes before returning a 422."""
    db.session.rollback()
    abort(422, message=message)


def _collection(features) -> dict:
    return {"type": "FeatureCollection", "features": [feature_to_geojson(f) for f in features]}


def _locked(message: str):
    db.session.rollback()
    abort(409, message=message)


def _apply(feature: MapFeature, geometry: dict | None, properties: dict | None) -> None:
    """Validate and copy GeoJSON input onto ``feature``; aborts with 422 on bad input and 409 when
    it would move or reshape a locked feature (unlock it in the same request to do both)."""
    was_locked = bool(feature.locked)
    try:
        props_in = properties or {}
        if "locked" in props_in:
            if not isinstance(props_in["locked"], bool):
                raise ValidationError("locked must be true or false")
            feature.locked = props_in["locked"]
        if "z" in props_in:
            z = props_in["z"]
            if not isinstance(z, int) or isinstance(z, bool) or abs(z) > 100_000:
                raise ValidationError("z must be a whole number")
            feature.z = z
        if was_locked and feature.locked and (geometry is not None or "radius_m" in props_in):
            _locked("This feature is locked: unlock it to move or reshape it")
    except ValidationError as exc:
        _reject(str(exc.messages[0] if exc.messages else exc))
    try:
        if geometry is not None:
            feature.geometry = parse_geometry(geometry)
            geometry_type = geometry["type"]
        else:
            geometry_type = None
        props = properties or {}
        unknown = set(props) - PROPERTY_KEYS
        if unknown:
            raise ValidationError(f"Unknown properties: {sorted(unknown)}")
        if "name" in props:
            feature.name = str(props["name"])[:120]
        if "kind" in props:
            feature.kind = props["kind"]
        if "radius_m" in props:
            radius = props["radius_m"]
            if radius is not None and (not isinstance(radius, int | float) or radius <= 0):
                raise ValidationError("radius_m must be a positive number")
            feature.radius_m = radius
        if "style" in props:
            if not isinstance(props["style"], dict):
                raise ValidationError("style must be an object")
            feature.style = props["style"]
        if feature.kind is None:
            feature.kind = FeatureKind.OTHER
        if geometry_type is None:
            from geoalchemy2.shape import to_shape

            geometry_type = to_shape(feature.geometry).geom_type
        check_feature_rules(feature.kind, geometry_type, feature.radius_m)
        if geometry_type != "Point":
            feature.radius_m = None
    except ValidationError as exc:
        _reject(str(exc.messages[0] if exc.messages else exc))


def _get(allotment, feature_id: int) -> MapFeature:
    feature = db.session.get(MapFeature, feature_id)
    if feature is None or feature.allotment_id != allotment.id:
        abort(404, message="Feature not found")
    return feature


@blp.route("")
class FeatureList(MethodView):
    @require_role(Role.VIEWER)
    @blp.response(200, FeatureCollectionSchema)
    def get(self, allotment, membership):
        features = (
            db.session.query(MapFeature)
            .filter_by(allotment_id=allotment.id)
            .order_by(MapFeature.id)
        )
        return _collection(features)

    @require_role(Role.EDITOR)
    @blp.arguments(FeatureInSchema)
    @blp.response(201, FeatureSchema)
    def post(self, data, allotment, membership):
        feature = MapFeature(allotment_id=allotment.id, created_by=membership.user_id, style={})
        _apply(feature, data["geometry"], data["properties"])
        db.session.add(feature)
        db.session.commit()
        events.emit(
            "feature.created",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={"feature_id": feature.id},
            payload={"kind": feature.kind},
        )
        return feature_to_geojson(feature)

    @require_role(Role.EDITOR)
    @blp.arguments(FeatureCollectionInSchema)
    @blp.response(200, FeatureCollectionSchema)
    def put(self, data, allotment, membership):
        """Replace the whole map: features with a known ``id`` are updated, those without are
        created, and existing features missing from the payload are deleted."""
        existing = {
            f.id: f for f in db.session.query(MapFeature).filter_by(allotment_id=allotment.id)
        }
        keep, created = set(), []
        for item in data["features"]:
            fid = item["id"]
            if fid is not None and fid not in existing:
                _reject(f"Feature {fid} does not belong to this allotment")
            feature = (
                existing[fid]
                if fid is not None
                else MapFeature(allotment_id=allotment.id, created_by=membership.user_id, style={})
            )
            _apply(feature, item["geometry"], item["properties"])
            if fid is None:
                db.session.add(feature)
                created.append(feature)
            else:
                keep.add(fid)
        deleted = [f for fid, f in existing.items() if fid not in keep]
        if any(f.locked for f in deleted):
            _locked("A locked feature can't be deleted: unlock it first")
        for feature in deleted:
            db.session.delete(feature)
        db.session.commit()
        events.emit(
            "feature.bulk_replaced",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            payload={"created": len(created), "updated": len(keep), "deleted": len(deleted)},
        )
        features = (
            db.session.query(MapFeature)
            .filter_by(allotment_id=allotment.id)
            .order_by(MapFeature.id)
        )
        return _collection(features)


@blp.route("/<int:feature_id>")
class FeatureDetail(MethodView):
    @require_role(Role.VIEWER)
    @blp.response(200, FeatureSchema)
    def get(self, allotment, membership, feature_id):
        return feature_to_geojson(_get(allotment, feature_id))

    @require_role(Role.EDITOR)
    @blp.arguments(FeaturePatchSchema)
    @blp.response(200, FeatureSchema)
    def patch(self, data, allotment, membership, feature_id):
        feature = _get(allotment, feature_id)
        _apply(feature, data.get("geometry"), data.get("properties"))
        db.session.commit()
        events.emit(
            "feature.updated",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={"feature_id": feature.id},
            payload={"fields": sorted(data)},
        )
        return feature_to_geojson(feature)

    @require_role(Role.EDITOR)
    @blp.response(204)
    def delete(self, allotment, membership, feature_id):
        feature = _get(allotment, feature_id)
        if feature.locked:
            _locked("A locked feature can't be deleted: unlock it first")
        db.session.delete(feature)
        db.session.commit()
        events.emit(
            "feature.deleted",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={"feature_id": feature_id},
        )
