from flask.views import MethodView
from flask_smorest import Blueprint, abort
from marshmallow import ValidationError

from .. import events
from ..extensions import db
from ..geojson import check_feature_rules, feature_to_geojson, parse_geometry
from ..models import MapFeature, MapSuggestion, Role
from ..schemas import (
    FeatureSchema,
    SuggestionIdsSchema,
    SuggestionPatchSchema,
    SuggestionQuerySchema,
    SuggestionSchema,
)
from ..security import require_role

blp = Blueprint(
    "suggestions",
    __name__,
    url_prefix="/api/v1/allotments/<int:allotment_id>/suggestions",
    description="Objects recognised in photos, waiting to be accepted as map features",
)


def to_dict(s: MapSuggestion) -> dict:
    return {
        "id": s.id,
        "job_id": s.job_id,
        "kind": s.kind,
        "name": s.name,
        "geometry": s.geometry,
        "radius_m": s.radius_m,
        "confidence": s.confidence,
        "views": s.views,
        "status": s.status,
        "feature_id": s.feature_id,
    }


def _get_all(allotment, ids: list[int]) -> list[MapSuggestion]:
    rows = (
        db.session.query(MapSuggestion)
        .filter(MapSuggestion.allotment_id == allotment.id, MapSuggestion.id.in_(set(ids)))
        .all()
    )
    if len(rows) != len(set(ids)):
        abort(404, message="Some of those suggestions don't exist")
    return rows


@blp.route("")
class SuggestionList(MethodView):
    @require_role(Role.EDITOR)
    @blp.arguments(SuggestionQuerySchema, location="query")
    @blp.response(200, SuggestionSchema(many=True))
    def get(self, args, allotment, membership):
        rows = (
            db.session.query(MapSuggestion)
            .filter_by(allotment_id=allotment.id, status=args["status"])
            .order_by(MapSuggestion.confidence.desc(), MapSuggestion.id)
        )
        return [to_dict(s) for s in rows]


@blp.route("/<int:suggestion_id>")
class SuggestionDetail(MethodView):
    @require_role(Role.EDITOR)
    @blp.arguments(SuggestionPatchSchema)
    @blp.response(200, SuggestionSchema)
    def patch(self, data, allotment, membership, suggestion_id):
        """Rename a suggestion or change what kind of thing it is before accepting it."""
        [s] = _get_all(allotment, [suggestion_id])
        if s.status != "pending":
            abort(409, message=f"A {s.status} suggestion can't be edited")
        for key, value in data.items():
            setattr(s, key, value)
        db.session.commit()
        return to_dict(s)


@blp.route("/accept")
class SuggestionAccept(MethodView):
    @require_role(Role.EDITOR)
    @blp.arguments(SuggestionIdsSchema)
    @blp.response(200, FeatureSchema(many=True))
    def post(self, data, allotment, membership):
        """Turn suggestions into map features. All or nothing: if one is invalid none are added."""
        rows = _get_all(allotment, data["ids"])
        if any(s.status != "pending" for s in rows):
            abort(409, message="Only pending suggestions can be accepted")
        features = []
        try:
            for s in rows:
                feature = MapFeature(
                    allotment_id=allotment.id,
                    created_by=membership.user_id,
                    kind=s.kind,
                    name=s.name,
                    style={},
                )
                feature.geometry = parse_geometry(s.geometry)
                feature.radius_m = s.radius_m if s.geometry["type"] == "Point" else None
                check_feature_rules(feature.kind, s.geometry["type"], feature.radius_m)
                db.session.add(feature)
                db.session.flush()
                s.status, s.feature_id = "accepted", feature.id
                features.append(feature)
        except ValidationError as exc:
            db.session.rollback()
            abort(422, message=str(exc.messages[0] if exc.messages else exc))
        db.session.commit()
        for feature in features:
            events.emit(
                "feature.created",
                actor_id=membership.user_id,
                allotment_id=allotment.id,
                subject={"feature_id": feature.id},
                payload={"kind": feature.kind, "from": "suggestion"},
            )
        events.emit(
            "suggestions.accepted",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            payload={"count": len(features)},
        )
        return [feature_to_geojson(f) for f in features]


@blp.route("/dismiss")
class SuggestionDismiss(MethodView):
    @require_role(Role.EDITOR)
    @blp.arguments(SuggestionIdsSchema)
    @blp.response(204)
    def post(self, data, allotment, membership):
        """Throw suggestions away (accepted ones are left alone: they are already on the map)."""
        rows = _get_all(allotment, data["ids"])
        count = 0
        for s in rows:
            if s.status == "pending":
                s.status = "dismissed"
                count += 1
        db.session.commit()
        events.emit(
            "suggestions.dismissed",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            payload={"count": count},
        )
