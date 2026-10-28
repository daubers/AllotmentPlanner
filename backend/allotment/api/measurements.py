from datetime import UTC, datetime

import numpy as np
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from geoalchemy2.shape import to_shape
from marshmallow import ValidationError
from shapely.geometry import mapping

from .. import events, measure
from ..extensions import db
from ..geojson import parse_geometry
from ..models import MapFeature, Measurement, Role
from ..schemas import (
    FitQuerySchema,
    FitResultSchema,
    MeasurementCustomSchema,
    MeasurementListSchema,
    MeasurementPatchSchema,
    MeasurementSchema,
)
from ..security import require_role

blp = Blueprint(
    "measurements",
    __name__,
    url_prefix="/api/v1/allotments/<int:allotment_id>/measurements",
    description="Measuring checklist: distances taken on site that correct the drawn shapes",
)

KIND_ORDER = {"edge": 0, "diagonal": 1, "radius": 2, "custom": 3}


def _geometry(feature: MapFeature) -> dict:
    return mapping(to_shape(feature.geometry))


def _features(allotment) -> list[MapFeature]:
    return (
        db.session.query(MapFeature)
        .filter_by(allotment_id=allotment.id)
        .order_by(MapFeature.id)
        .all()
    )


def _live(m: Measurement) -> bool:
    """Counts towards the checklist and the fit: its corners exist and it hasn't been skipped."""
    return not m.stale and not m.skipped


def _sorted(items: list[Measurement]) -> list[Measurement]:
    return sorted(items, key=lambda m: (m.feature_id, KIND_ORDER[m.kind], m.a, m.b))


def _item_dict(m: Measurement, feature: MapFeature | None, drawn: float | None) -> dict:
    return {
        "id": m.id,
        "feature_id": m.feature_id,
        "feature_name": (feature.name if feature else "") or f"Feature {m.feature_id}",
        "feature_kind": feature.kind if feature else "other",
        "kind": m.kind,
        "a": m.a,
        "b": m.b,
        "label": "Radius" if m.kind == "radius" else f"{m.a + 1} to {m.b + 1}",
        "drawn_m": drawn,
        "value_m": m.value_m,
        "note": m.note,
        "skipped": m.skipped,
        "stale": m.stale,
        "measured_at": m.measured_at,
        "measured_by": m.measured_by,
    }


def _drawn(feature: MapFeature, m: Measurement) -> float | None:
    geometry = _geometry(feature)
    points = measure.corners(geometry)
    if m.kind == "radius":
        return feature.radius_m
    if m.a >= len(points) or m.b >= len(points):
        return None
    xy = measure.to_metres(points, measure.centre(points))
    return measure.drawn_length(xy, measure.Spec(m.kind, m.a, m.b), feature.radius_m)


def _listing(allotment) -> dict:
    features = {f.id: f for f in _features(allotment)}
    rows = _sorted(db.session.query(Measurement).filter_by(allotment_id=allotment.id).all())
    items, per_feature = [], {}
    drawn_cache: dict[int, tuple] = {}
    for m in rows:
        feature = features.get(m.feature_id)
        if feature is None:
            continue
        if feature.id not in drawn_cache:
            points = measure.corners(_geometry(feature))
            drawn_cache[feature.id] = (points, measure.to_metres(points, measure.centre(points)))
        points, xy = drawn_cache[feature.id]
        if m.kind == "radius":
            drawn = feature.radius_m
        elif m.a < len(points) and m.b < len(points):
            drawn = measure.drawn_length(xy, measure.Spec(m.kind, m.a, m.b), None)
        else:
            drawn = None
        items.append(_item_dict(m, feature, drawn))
        row = per_feature.setdefault(
            feature.id,
            {
                "id": feature.id,
                "name": feature.name or f"Feature {feature.id}",
                "kind": feature.kind,
                "corners": len(points),
                "measured": 0,
                "total": 0,
            },
        )
        if _live(m):
            row["total"] += 1
            row["measured"] += m.value_m is not None
    total = sum(r["total"] for r in per_feature.values())
    measured = sum(r["measured"] for r in per_feature.values())
    return {
        "length_unit": allotment.length_unit,
        "items": items,
        "features": list(per_feature.values()),
        "total": total,
        "measured": measured,
    }


def _get(allotment, measurement_id: int) -> Measurement:
    m = db.session.get(Measurement, measurement_id)
    if m is None or m.allotment_id != allotment.id:
        abort(404, message="Measurement not found")
    return m


@blp.route("")
class MeasurementList(MethodView):
    @require_role(Role.VIEWER)
    @blp.response(200, MeasurementListSchema)
    def get(self, allotment, membership):
        """The checklist, with each distance's current length on the map."""
        return _listing(allotment)

    @require_role(Role.EDITOR)
    @blp.arguments(MeasurementCustomSchema)
    @blp.response(201, MeasurementSchema)
    def post(self, data, allotment, membership):
        """Add an extra distance between any two corners of a shape (a spare, to check a fit)."""
        feature = db.session.get(MapFeature, data["feature_id"])
        if feature is None or feature.allotment_id != allotment.id:
            abort(404, message="Feature not found")
        count = len(measure.corners(_geometry(feature)))
        a, b = sorted((data["a"], data["b"]))
        if a == b or b >= count or count < 2:
            abort(422, message=f"Pick two different corners from 1 to {count}")
        for m in db.session.query(Measurement).filter_by(feature_id=feature.id, stale=False):
            if m.kind != "radius" and {m.a, m.b} == {a, b}:
                abort(409, message="That distance is already on the list")
        m = Measurement(allotment_id=allotment.id, feature_id=feature.id, kind="custom", a=a, b=b)
        db.session.add(m)
        db.session.commit()
        return _item_dict(m, feature, _drawn(feature, m))


@blp.route("/sync")
class MeasurementSync(MethodView):
    @require_role(Role.EDITOR)
    @blp.response(200, MeasurementListSchema)
    def post(self, allotment, membership):
        """Make the checklist match the drawn shapes. Safe to repeat: nothing measured is lost.

        New shapes get their distances; distances for corners that no longer exist are removed
        if unmeasured and kept (flagged stale) if they were measured."""
        created = removed = flagged = 0
        for feature in _features(allotment):
            geometry = _geometry(feature)
            points = measure.corners(geometry)
            wanted = {
                (s.kind, s.a, s.b)
                for s in measure.expected(geometry["type"], len(points), feature.radius_m)
            }
            existing = {
                (m.kind, m.a, m.b): m
                for m in db.session.query(Measurement).filter_by(feature_id=feature.id)
            }
            for key in sorted(wanted - set(existing), key=lambda k: (KIND_ORDER[k[0]], k[1])):
                db.session.add(
                    Measurement(
                        allotment_id=allotment.id,
                        feature_id=feature.id,
                        kind=key[0],
                        a=key[1],
                        b=key[2],
                    )
                )
                created += 1
            for key, m in existing.items():
                still_there = key in wanted or (
                    m.kind == "custom" and max(m.a, m.b) < len(points) and len(points) >= 2
                )
                if still_there:
                    m.stale = False
                elif m.value_m is None:
                    db.session.delete(m)
                    removed += 1
                elif not m.stale:
                    m.stale = True
                    flagged += 1
        db.session.commit()
        events.emit(
            "measurement.synced",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            payload={"created": created, "removed": removed, "stale": flagged},
        )
        return _listing(allotment)


@blp.route("/<int:measurement_id>")
class MeasurementDetail(MethodView):
    @require_role(Role.EDITOR)
    @blp.arguments(MeasurementPatchSchema)
    @blp.response(200, MeasurementSchema)
    def patch(self, data, allotment, membership, measurement_id):
        """Record a measurement, add a note, or skip it."""
        m = _get(allotment, measurement_id)
        if "value_m" in data:
            m.value_m = data["value_m"]
            if data["value_m"] is None:
                m.measured_at = m.measured_by = None
            else:
                m.measured_at, m.measured_by = datetime.now(UTC), membership.user_id
                m.skipped = False
        if "note" in data:
            m.note = data["note"]
        if "skipped" in data:
            m.skipped = data["skipped"]
        db.session.commit()
        if data.get("value_m") is not None:
            events.emit(
                "measurement.recorded",
                actor_id=membership.user_id,
                allotment_id=allotment.id,
                subject={"measurement_id": m.id, "feature_id": m.feature_id},
                payload={"kind": m.kind, "value_m": m.value_m},
            )
        feature = db.session.get(MapFeature, m.feature_id)
        return _item_dict(m, feature, _drawn(feature, m))

    @require_role(Role.EDITOR)
    @blp.response(204)
    def delete(self, allotment, membership, measurement_id):
        """Remove an extra distance you added. The generated ones can only be skipped."""
        m = _get(allotment, measurement_id)
        if m.kind != "custom":
            abort(409, message="Only extra distances can be removed; skip this one instead")
        db.session.delete(m)
        db.session.commit()


def _fit_feature(feature: MapFeature, items: list[Measurement]) -> dict:
    """What fitting would do to one feature, without touching it."""
    geometry = _geometry(feature)
    points = measure.corners(geometry)
    result = {
        "feature_id": feature.id,
        "name": feature.name or f"Feature {feature.id}",
        "changed": False,
        "rms_before_m": 0.0,
        "rms_after_m": 0.0,
        "max_move_m": 0.0,
        "missing": 0,
        "recheck": [],
        "geometry": geometry,
        "drawn_geometry": geometry,
        "radius_m": feature.radius_m,
        "error": None,
    }
    radius = next((m for m in items if m.kind == "radius"), None)
    if radius is not None:
        result["radius_m"] = radius.value_m
        result["changed"] = abs((feature.radius_m or 0) - radius.value_m) > 1e-6
        result["rms_before_m"] = abs((feature.radius_m or 0) - radius.value_m)
        return result
    pairs = [m for m in items if m.a < len(points) and m.b < len(points)]
    if not pairs:
        return result
    origin = measure.centre(points)
    xy = measure.to_metres(points, origin)
    closed = geometry["type"] == "Polygon"
    fit = measure.fit_shape(xy, [(m.a, m.b, m.value_m) for m in pairs], closed=closed)
    new_points = measure.from_metres(fit.xy, origin)
    ring = [*new_points, new_points[0]] if closed else new_points
    new_geometry = {"type": geometry["type"], "coordinates": [ring] if closed else ring}
    try:
        parse_geometry(new_geometry)
    except ValidationError as exc:
        result["error"] = f"The corrected shape is not valid: {exc.messages[0]}"
    result.update(
        geometry=new_geometry,
        rms_before_m=float(np.sqrt(np.mean(fit.before**2))),
        rms_after_m=float(np.sqrt(np.mean(fit.after**2))),
        max_move_m=float(np.linalg.norm(fit.xy - xy, axis=1).max()),
        missing=fit.missing,
        recheck=[pairs[i].id for i in fit.recheck],
    )
    result["changed"] = result["max_move_m"] > 0.001
    return result


@blp.route("/fit")
class MeasurementFit(MethodView):
    @require_role(Role.EDITOR)
    @blp.arguments(FitQuerySchema, location="query")
    @blp.response(200, FitResultSchema)
    def post(self, args, allotment, membership):
        """Correct the drawn shapes to match the measurements.

        ``preview=true`` (the default) only reports what would change. ``preview=false`` applies
        it, all or nothing: if any corrected shape is invalid nothing is changed."""
        features = {f.id: f for f in _features(allotment)}
        by_feature: dict[int, list[Measurement]] = {}
        rows = db.session.query(Measurement).filter_by(allotment_id=allotment.id)
        for m in _sorted(rows.all()):
            if _live(m) and m.value_m is not None and m.feature_id in features:
                by_feature.setdefault(m.feature_id, []).append(m)
        results = [_fit_feature(features[fid], items) for fid, items in by_feature.items()]
        if not args["preview"]:
            bad = [r for r in results if r["error"]]
            if bad:
                abort(422, message=f"{bad[0]['name']}: {bad[0]['error']}. Nothing was changed.")
            changed = [r for r in results if r["changed"]]
            for r in changed:
                feature = features[r["feature_id"]]
                feature.geometry = parse_geometry(r["geometry"])
                feature.radius_m = r["radius_m"]
            db.session.commit()
            if changed:
                events.emit(
                    "measurements.applied",
                    actor_id=membership.user_id,
                    allotment_id=allotment.id,
                    payload={"features": len(changed)},
                )
        return {"applied": not args["preview"], "features": results}
