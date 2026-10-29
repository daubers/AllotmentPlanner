from flask.views import MethodView
from flask_smorest import Blueprint, abort
from sqlalchemy import or_

from .. import events
from ..extensions import db
from ..models import Media, Role, SeedPacket
from ..schemas import PacketInSchema, PacketPatchSchema, PacketQuerySchema, PacketSchema
from ..security import require_role
from ..seeds import is_due, normalise_calendar, range_problem
from .media import media_to_dict

blp = Blueprint(
    "packets",
    __name__,
    url_prefix="/api/v1/allotments/<int:allotment_id>/packets",
    description="The seed library",
)

FIELDS = (
    "name",
    "variety",
    "supplier",
    "latin_name",
    "notes",
    "raw_text",
    "sow_depth_mm",
    "spacing_plant_cm",
    "spacing_row_cm",
    "germinate_days_min",
    "germinate_days_max",
    "maturity_days_min",
    "maturity_days_max",
    "sun",
    "stock",
    "best_before_year",
)
RANGES = (
    ("germinate_days_min", "germinate_days_max", "Days to germinate"),
    ("maturity_days_min", "maturity_days_max", "Days to maturity"),
)


def packet_to_dict(p: SeedPacket, photos: list[Media] | None = None) -> dict:
    if photos is None:
        photos = _photos([p.id]).get(p.id, [])
    return {
        "id": p.id,
        "status": p.status,
        **{f: getattr(p, f) for f in FIELDS},
        "calendar": normalise_calendar(p.calendar),
        "photos": [media_to_dict(m) for m in photos],
        "created_by": p.created_by,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


def _photos(packet_ids: list[int]) -> dict[int, list[Media]]:
    """Photos for several packets in one query, oldest first (so the front comes first)."""
    out: dict[int, list[Media]] = {}
    if packet_ids:
        rows = (
            db.session.query(Media)
            .filter(Media.packet_id.in_(packet_ids))
            .order_by(Media.taken_at, Media.id)
            .all()
        )
        for m in rows:
            out.setdefault(m.packet_id, []).append(m)
    return out


def _apply(packet: SeedPacket, data: dict) -> None:
    for key in FIELDS:
        if key in data:
            setattr(packet, key, data[key])
    if "calendar" in data:
        packet.calendar = normalise_calendar(data["calendar"])
    for low, high, what in RANGES:
        problem = range_problem(getattr(packet, low), getattr(packet, high), what)
        if problem:
            db.session.rollback()
            abort(422, message=problem)


def _get(allotment, packet_id: int) -> SeedPacket:
    packet = db.session.get(SeedPacket, packet_id)
    if packet is None or packet.allotment_id != allotment.id:
        abort(404, message="Seed packet not found")
    return packet


@blp.route("")
class PacketList(MethodView):
    @require_role(Role.VIEWER)
    @blp.arguments(PacketQuerySchema, location="query")
    @blp.response(200, PacketSchema(many=True))
    def get(self, args, allotment, membership):
        q = db.session.query(SeedPacket).filter_by(allotment_id=allotment.id)
        if args.get("q", "").strip():
            like = f"%{args['q'].strip()}%"
            q = q.filter(
                or_(
                    *(
                        getattr(SeedPacket, col).ilike(like)
                        for col in ("name", "variety", "supplier", "latin_name", "notes")
                    )
                )
            )
        if "stock" in args:
            q = q.filter(SeedPacket.stock == args["stock"])
        packets = q.order_by(SeedPacket.name, SeedPacket.variety, SeedPacket.id).all()
        if "month" in args:  # the calendar is a JSON list, so this is filtered here
            packets = [p for p in packets if is_due(p.calendar, args["month"], args["activity"])]
        photos = _photos([p.id for p in packets])
        return [packet_to_dict(p, photos.get(p.id, [])) for p in packets]

    @require_role(Role.EDITOR)
    @blp.arguments(PacketInSchema)
    @blp.response(201, PacketSchema)
    def post(self, data, allotment, membership):
        packet = SeedPacket(allotment_id=allotment.id, created_by=membership.user_id)
        packet.calendar = normalise_calendar(None)
        _apply(packet, data)
        db.session.add(packet)
        db.session.commit()
        events.emit(
            "packet.created",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={"packet_id": packet.id},
            payload={"name": packet.name, "variety": packet.variety},
        )
        return packet_to_dict(packet)


@blp.route("/<int:packet_id>")
class PacketDetail(MethodView):
    @require_role(Role.VIEWER)
    @blp.response(200, PacketSchema)
    def get(self, allotment, membership, packet_id):
        return packet_to_dict(_get(allotment, packet_id))

    @require_role(Role.EDITOR)
    @blp.arguments(PacketPatchSchema)
    @blp.response(200, PacketSchema)
    def patch(self, data, allotment, membership, packet_id):
        packet = _get(allotment, packet_id)
        _apply(packet, data)
        db.session.commit()
        events.emit(
            "packet.updated",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={"packet_id": packet.id},
            payload={"fields": sorted(data)},
        )
        return packet_to_dict(packet)

    @require_role(Role.EDITOR)
    @blp.response(204)
    def delete(self, allotment, membership, packet_id):
        """Remove the packet. Its photos stay in the photo timeline, no longer linked to it."""
        packet = _get(allotment, packet_id)
        db.session.delete(packet)
        db.session.commit()
        events.emit(
            "packet.deleted",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={"packet_id": packet_id},
        )
