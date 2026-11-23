from datetime import date

from flask.views import MethodView
from flask_smorest import Blueprint, abort
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping

from .. import events
from ..extensions import db
from ..geojson import parse_geometry
from ..models import MapFeature, Media, PlanItem, Planting, Role, SeedPacket
from ..plantings import GROWING, area_m2, overlap_warning, overlaps, region_problem, to_polygon
from ..schemas import (
    PlantingInSchema,
    PlantingPatchSchema,
    PlantingQuerySchema,
    PlantingSchema,
    TaskSchema,
    TaskSuggestionSchema,
)
from ..security import require_role
from ..seeds import normalise_calendar
from ..task_suggestions import Sowing, suggest_for_planting
from .media import media_to_dict
from .tasks import add_suggested, suggestions_with_state, task_to_dict

blp = Blueprint(
    "plantings",
    __name__,
    url_prefix="/api/v1/allotments/<int:allotment_id>/plantings",
    description="What is growing where in the beds",
)


def region_geojson(planting: Planting) -> dict:
    return mapping(to_shape(planting.region))


def _label(packet: SeedPacket | None) -> str:
    if packet is None:
        return "an unnamed planting"
    return f"{packet.name} ({packet.variety})" if packet.variety else packet.name


def planting_to_dict(p: Planting, warnings: list[str] | None = None, detail: bool = False) -> dict:
    packet = db.session.get(SeedPacket, p.packet_id) if p.packet_id else None
    bed = db.session.get(MapFeature, p.feature_id)
    region = region_geojson(p)
    out = {
        "id": p.id,
        "feature_id": p.feature_id,
        "bed_name": bed.name if bed else "",
        "packet_id": p.packet_id,
        "packet_name": packet.name if packet else None,
        "packet_variety": packet.variety if packet else None,
        "tray_id": p.tray_id,
        "region": region,
        "area_m2": round(area_m2(to_polygon(region)), 2),
        "count": p.count,
        "method": p.method,
        "status": p.status,
        "sown_on": p.sown_on,
        "planted_on": p.planted_on,
        "harvested_on": p.harvested_on,
        "notes": p.notes,
        "warnings": warnings or [],
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }
    if detail:
        rows = (
            db.session.query(Media).filter_by(planting_id=p.id).order_by(Media.taken_at, Media.id)
        )
        out["photos"] = [media_to_dict(m) for m in rows]
    return out


def _get(allotment, planting_id: int) -> Planting:
    planting = db.session.get(Planting, planting_id)
    if planting is None or planting.allotment_id != allotment.id:
        abort(404, message="Planting not found")
    return planting


def get_bed(allotment, feature_id: int) -> MapFeature:
    bed = db.session.get(MapFeature, feature_id)
    if bed is None or bed.allotment_id != allotment.id:
        abort(422, message="feature_id does not belong to this allotment")
    return bed


def check_region(bed: MapFeature, region: dict) -> None:
    problem = region_problem(region, mapping(to_shape(bed.geometry)))
    if problem:
        abort(422, message=problem)


def check_packet(allotment, packet_id: int | None) -> None:
    if packet_id is not None:
        packet = db.session.get(SeedPacket, packet_id)
        if packet is None or packet.allotment_id != allotment.id:
            abort(422, message="packet_id does not belong to this allotment")


def check_plan_item(allotment, bed: MapFeature, plan_item_id: int | None) -> PlanItem | None:
    """The planned crop a planting carries out, if it may: right bed, planned, direct sown."""
    if plan_item_id is None:
        return None
    item = db.session.get(PlanItem, plan_item_id)
    if item is None or item.allotment_id != allotment.id:
        abort(422, message="plan_item_id does not belong to this allotment")
    if item.feature_id != bed.id:
        abort(422, message="That plan item is for a different bed")
    if item.status != "planned":
        abort(409, message="That plan item has already been planted or skipped")
    if item.method == "transplant":
        abort(
            422, message="A transplant is planted out of a tray: sow it in a tray, then plant out"
        )
    return item


def overlap_warnings(feature_id: int, region: dict, ignore_id: int | None = None) -> list[str]:
    """Other plantings still in the ground that this region overlaps."""
    others = db.session.query(Planting).filter(
        Planting.feature_id == feature_id, Planting.status.in_(GROWING)
    )
    packets = {}
    entries = []
    for other in others:
        if other.id == ignore_id:
            continue
        if other.packet_id not in packets:
            packets[other.packet_id] = (
                db.session.get(SeedPacket, other.packet_id) if other.packet_id else None
            )
        entries.append((other.id, _label(packets[other.packet_id]), region_geojson(other)))
    return [overlap_warning(label, shared) for _, label, shared in overlaps(region, entries)]


def parse_region(region: dict):
    from marshmallow import ValidationError

    try:
        return parse_geometry(region)
    except ValidationError as exc:
        abort(422, message=str(exc.messages[0] if exc.messages else exc))


@blp.route("")
class PlantingList(MethodView):
    @require_role(Role.VIEWER)
    @blp.arguments(PlantingQuerySchema, location="query")
    @blp.response(200, PlantingSchema(many=True))
    def get(self, args, allotment, membership):
        q = db.session.query(Planting).filter_by(allotment_id=allotment.id)
        for key in ("feature_id", "packet_id", "tray_id", "status"):
            if key in args:
                q = q.filter(getattr(Planting, key) == args[key])
        if "growing" in args:
            growing = Planting.status.in_(GROWING)
            q = q.filter(growing if args["growing"] else ~growing)
        rows = q.order_by(Planting.feature_id, Planting.id).all()
        return [planting_to_dict(p) for p in rows]

    @require_role(Role.EDITOR)
    @blp.arguments(PlantingInSchema)
    @blp.response(201, PlantingSchema)
    def post(self, data, allotment, membership):
        """Direct sow: draw a region in a bed and say what went in. Overlaps are warned about."""
        bed = get_bed(allotment, data["feature_id"])
        check_packet(allotment, data["packet_id"])
        check_region(bed, data["region"])
        plan_item = check_plan_item(allotment, bed, data["plan_item_id"])
        planting = Planting(
            allotment_id=allotment.id,
            feature_id=bed.id,
            packet_id=data["packet_id"],
            region=parse_region(data["region"]),
            count=data["count"],
            method="direct_sow",
            status="sown",
            sown_on=data["sown_on"] or date.today(),
            notes=data["notes"],
            created_by=membership.user_id,
        )
        warnings = overlap_warnings(bed.id, data["region"])
        db.session.add(planting)
        if plan_item is not None:
            db.session.flush()  # for the planting's id; the item and the planting save together
            plan_item.status = "done"
            plan_item.planting_id = planting.id
        db.session.commit()
        events.emit(
            "planting.created",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={
                "planting_id": planting.id,
                "feature_id": bed.id,
                "packet_id": planting.packet_id,
            },
            payload={"method": "direct_sow", "bed": bed.name},
        )
        return planting_to_dict(planting, warnings)


@blp.route("/<int:planting_id>")
class PlantingDetail(MethodView):
    @require_role(Role.VIEWER)
    @blp.response(200, PlantingSchema)
    def get(self, allotment, membership, planting_id):
        return planting_to_dict(_get(allotment, planting_id), detail=True)

    @require_role(Role.EDITOR)
    @blp.arguments(PlantingPatchSchema)
    @blp.response(200, PlantingSchema)
    def patch(self, data, allotment, membership, planting_id):
        planting = _get(allotment, planting_id)
        before = planting.status
        warnings: list[str] = []
        if "packet_id" in data:
            check_packet(allotment, data["packet_id"])
            planting.packet_id = data["packet_id"]
        if "region" in data:
            bed = db.session.get(MapFeature, planting.feature_id)
            check_region(bed, data["region"])
            planting.region = parse_region(data["region"])
            warnings = overlap_warnings(bed.id, data["region"], ignore_id=planting.id)
        for key in ("count", "status", "sown_on", "planted_on", "harvested_on", "notes"):
            if key in data:
                setattr(planting, key, data[key])
        db.session.commit()
        events.emit(
            "planting.updated",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={"planting_id": planting.id, "feature_id": planting.feature_id},
            payload={"fields": sorted(data)},
        )
        if planting.status == "harvesting" and before != "harvesting":
            events.emit(
                "planting.harvested",
                actor_id=membership.user_id,
                allotment_id=allotment.id,
                subject={"planting_id": planting.id, "feature_id": planting.feature_id},
            )
        return planting_to_dict(planting, warnings, detail=True)

    @require_role(Role.EDITOR)
    @blp.response(204)
    def delete(self, allotment, membership, planting_id):
        """Remove the planting. Photos stay in the timeline; tray cells stay planted out."""
        planting = _get(allotment, planting_id)
        db.session.delete(planting)
        db.session.commit()
        events.emit(
            "planting.deleted",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={"planting_id": planting_id},
        )


def _planting_suggestions(planting: Planting):
    when = planting.sown_on or planting.planted_on
    if when is None:
        return []
    packet = db.session.get(SeedPacket, planting.packet_id) if planting.packet_id else None
    cal = normalise_calendar(packet.calendar if packet else None)
    name = packet.name if packet else "planting"
    bed = db.session.get(MapFeature, planting.feature_id)
    sowing = Sowing(
        packet_id=planting.packet_id or 0,
        name=name,
        sown_on=when,
        germinate_days_min=packet.germinate_days_min if packet else None,
        maturity_days_min=packet.maturity_days_min if packet else None,
        plant_out_months=tuple(cal["plant_out"]),
        harvest_months=tuple(cal["harvest"]),
    )
    label = f"{name} in {bed.name or 'bed'}" if bed else name
    return suggest_for_planting(
        planting.id,
        label,
        sowing,
        planting.method,
        planting.status,
        planting.harvested_on is not None,
        date.today(),
    )


@blp.route("/<int:planting_id>/suggested-tasks")
class PlantingSuggestedTasks(MethodView):
    @require_role(Role.VIEWER)
    @blp.response(200, TaskSuggestionSchema(many=True))
    def get(self, allotment, membership, planting_id):
        """Jobs the packet's dates suggest for this planting, marked if already added."""
        return suggestions_with_state(
            allotment, _planting_suggestions(_get(allotment, planting_id))
        )

    @require_role(Role.EDITOR)
    @blp.response(201, TaskSchema(many=True))
    def post(self, allotment, membership, planting_id):
        """Add every suggestion not yet added as a task pinned to this planting."""
        planting = _get(allotment, planting_id)
        tasks = add_suggested(
            allotment, membership, _planting_suggestions(planting), planting_id=planting.id
        )
        return [task_to_dict(t) for t in tasks]
