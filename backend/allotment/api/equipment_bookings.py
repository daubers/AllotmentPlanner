from flask.views import MethodView
from flask_smorest import Blueprint, abort

from .. import events
from ..equipment_bookings import booking_conflicts, date_problem, overlapping
from ..extensions import db
from ..models import Equipment, EquipmentBooking, MapFeature, Planting, Role, SeedPacket
from ..schemas import (
    BookingInSchema,
    BookingPatchSchema,
    BookingQuerySchema,
    BookingSchema,
    EquipmentBookingsSchema,
)
from ..security import require_role
from .equipment import _get as _get_equipment

blp = Blueprint(
    "equipment_bookings",
    __name__,
    url_prefix="/api/v1/allotments/<int:allotment_id>",
    description="Equipment in use on beds and plantings, and when it is over-booked",
)


def _names(bookings: list[EquipmentBooking]) -> tuple[dict, dict, dict]:
    """Equipment, bed and planting names for these bookings, in three queries."""
    equipment = {
        e.id: e
        for e in db.session.query(Equipment).filter(
            Equipment.id.in_({b.equipment_id for b in bookings})
        )
    }
    features = {b.feature_id for b in bookings if b.feature_id}
    names = (
        dict(db.session.query(MapFeature.id, MapFeature.name).filter(MapFeature.id.in_(features)))
        if features
        else {}
    )
    plantings = {b.planting_id for b in bookings if b.planting_id}
    labels = {}
    if plantings:
        rows = (
            db.session.query(Planting.id, SeedPacket.name, MapFeature.name)
            .outerjoin(SeedPacket, SeedPacket.id == Planting.packet_id)
            .join(MapFeature, MapFeature.id == Planting.feature_id)
            .filter(Planting.id.in_(plantings))
        )
        labels = {pid: f"{pk or 'Planting'} in {bed}" for pid, pk, bed in rows}
    return equipment, names, labels


def booking_dicts(
    bookings: list[EquipmentBooking], warnings: dict[int, list] | None = None
) -> list[dict]:
    equipment, names, labels = _names(bookings) if bookings else ({}, {}, {})
    return [
        {
            "id": b.id,
            "equipment_id": b.equipment_id,
            "equipment_name": equipment[b.equipment_id].name,
            "equipment_quantity": equipment[b.equipment_id].quantity,
            "feature_id": b.feature_id,
            "feature_name": (names.get(b.feature_id) or f"Feature {b.feature_id}")
            if b.feature_id
            else None,
            "planting_id": b.planting_id,
            "planting_label": labels.get(b.planting_id) if b.planting_id else None,
            "starts_on": b.starts_on,
            "ends_on": b.ends_on,
            "quantity": b.quantity,
            "note": b.note,
            "warnings": (warnings or {}).get(b.id, []),
        }
        for b in bookings
    ]


def _all_for(equipment_id: int) -> list[EquipmentBooking]:
    return (
        db.session.query(EquipmentBooking)
        .filter_by(equipment_id=equipment_id)
        .order_by(EquipmentBooking.starts_on, EquipmentBooking.id)
        .all()
    )


def _get(allotment, booking_id: int) -> EquipmentBooking:
    booking = db.session.get(EquipmentBooking, booking_id)
    if booking is None or booking.allotment_id != allotment.id:
        abort(404, message="Booking not found")
    return booking


def _check_target(allotment, feature_id, planting_id) -> None:
    if feature_id is not None:
        feature = db.session.get(MapFeature, feature_id)
        if feature is None or feature.allotment_id != allotment.id:
            abort(422, message="feature_id does not belong to this allotment")
    if planting_id is not None:
        planting = db.session.get(Planting, planting_id)
        if planting is None or planting.allotment_id != allotment.id:
            abort(422, message="planting_id does not belong to this allotment")


def _emit(kind: str, allotment, membership, booking: EquipmentBooking, **payload) -> None:
    events.emit(
        f"equipment_booking.{kind}",
        actor_id=membership.user_id,
        allotment_id=allotment.id,
        subject={"booking_id": booking.id, "equipment_id": booking.equipment_id},
        payload=payload,
    )


def _with_warnings(booking: EquipmentBooking, item: Equipment) -> dict:
    conflicts = overlapping(booking_conflicts(_all_for(item.id), item.quantity), booking)
    return booking_dicts([booking], {booking.id: conflicts})[0]


@blp.route("/equipment-bookings")
class BookingList(MethodView):
    @require_role(Role.VIEWER)
    @blp.arguments(BookingQuerySchema, location="query")
    @blp.response(200, BookingSchema(many=True))
    def get(self, args, allotment, membership):
        """Bookings, optionally for one item, bed or planting and within a window."""
        rows = db.session.query(EquipmentBooking).filter_by(allotment_id=allotment.id)
        for key in ("equipment_id", "feature_id", "planting_id"):
            if key in args:
                rows = rows.filter(getattr(EquipmentBooking, key) == args[key])
        if "start" in args:
            rows = rows.filter(EquipmentBooking.ends_on > args["start"])
        if "to" in args:
            rows = rows.filter(EquipmentBooking.starts_on <= args["to"])
        return booking_dicts(rows.order_by(EquipmentBooking.starts_on, EquipmentBooking.id).all())


@blp.route("/equipment/<int:equipment_id>/bookings")
class EquipmentBookings(MethodView):
    @require_role(Role.VIEWER)
    @blp.response(200, EquipmentBookingsSchema)
    def get(self, allotment, membership, equipment_id):
        """Where this item is in use, and when more is booked than you own."""
        item = _get_equipment(allotment, equipment_id)
        bookings = _all_for(item.id)
        return {
            "quantity": item.quantity,
            "bookings": booking_dicts(bookings),
            "conflicts": booking_conflicts(bookings, item.quantity),
        }

    @require_role(Role.EDITOR)
    @blp.arguments(BookingInSchema)
    @blp.response(201, BookingSchema)
    def post(self, data, allotment, membership, equipment_id):
        """Put some of this item to use. Booking more than you own is allowed, with a warning."""
        item = _get_equipment(allotment, equipment_id)
        _check_target(allotment, data["feature_id"], data["planting_id"])
        problem = date_problem(data["starts_on"], data["ends_on"])
        if problem:
            abort(422, message=problem)
        booking = EquipmentBooking(
            allotment_id=allotment.id, equipment_id=item.id, created_by=membership.user_id, **data
        )
        db.session.add(booking)
        db.session.commit()
        _emit("created", allotment, membership, booking, quantity=booking.quantity)
        return _with_warnings(booking, item)


@blp.route("/equipment-bookings/<int:booking_id>")
class BookingDetail(MethodView):
    @require_role(Role.EDITOR)
    @blp.arguments(BookingPatchSchema)
    @blp.response(200, BookingSchema)
    def patch(self, data, allotment, membership, booking_id):
        booking = _get(allotment, booking_id)
        item = db.session.get(Equipment, booking.equipment_id)
        starts = data.get("starts_on", booking.starts_on)
        ends = data.get("ends_on", booking.ends_on)
        problem = date_problem(starts, ends)
        if problem:
            abort(422, message=problem)  # checked before anything changes
        for key in ("starts_on", "ends_on", "quantity", "note"):
            if key in data:
                setattr(booking, key, data[key])
        db.session.commit()
        _emit("updated", allotment, membership, booking, fields=sorted(data))
        return _with_warnings(booking, item)

    @require_role(Role.EDITOR)
    @blp.response(204)
    def delete(self, allotment, membership, booking_id):
        booking = _get(allotment, booking_id)
        db.session.delete(booking)
        db.session.commit()
        _emit("deleted", allotment, membership, booking)
