from flask.views import MethodView
from flask_jwt_extended import jwt_required
from flask_smorest import Blueprint, abort

from .. import events
from ..extensions import db
from ..models import Allotment, Media, Membership, Role, User
from ..schemas import (
    AllotmentCreateSchema,
    AllotmentSchema,
    AllotmentUpdateSchema,
    MemberAddSchema,
    MemberSchema,
    MemberUpdateSchema,
)
from ..security import current_user, require_role
from ..storage import safe_delete, safe_delete_prefix

blp = Blueprint(
    "allotments", __name__, url_prefix="/api/v1/allotments", description="Allotments and members"
)


def _dump(allotment: Allotment, role: str) -> dict:
    return {
        "id": allotment.id,
        "name": allotment.name,
        "description": allotment.description,
        "length_unit": allotment.length_unit,
        "role": role,
    }


def _member(m: Membership) -> dict:
    return {
        "user_id": m.user_id,
        "email": m.user.email,
        "display_name": m.user.display_name,
        "role": m.role,
    }


def _owner_count(allotment_id: int) -> int:
    return db.session.query(Membership).filter_by(allotment_id=allotment_id, role="owner").count()


@blp.route("")
class AllotmentList(MethodView):
    @jwt_required()
    @blp.response(200, AllotmentSchema(many=True))
    def get(self):
        user = current_user()
        return [_dump(m.allotment, m.role) for m in user.memberships]

    @jwt_required()
    @blp.arguments(AllotmentCreateSchema)
    @blp.response(201, AllotmentSchema)
    def post(self, data):
        user = current_user()
        allotment = Allotment(**data)
        db.session.add(allotment)
        db.session.flush()
        db.session.add(Membership(user_id=user.id, allotment_id=allotment.id, role=Role.OWNER))
        db.session.commit()
        events.emit(
            "allotment.created",
            actor_id=user.id,
            allotment_id=allotment.id,
            subject={"allotment_id": allotment.id},
        )
        return _dump(allotment, Role.OWNER)


@blp.route("/<int:allotment_id>")
class AllotmentDetail(MethodView):
    @require_role(Role.VIEWER)
    @blp.response(200, AllotmentSchema)
    def get(self, allotment, membership):
        return _dump(allotment, membership.role)

    @require_role(Role.OWNER)
    @blp.arguments(AllotmentUpdateSchema)
    @blp.response(200, AllotmentSchema)
    def patch(self, data, allotment, membership):
        for key, value in data.items():
            setattr(allotment, key, value)
        db.session.commit()
        events.emit(
            "allotment.updated",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            payload={"fields": sorted(data)},
        )
        return _dump(allotment, membership.role)

    @require_role(Role.OWNER)
    @blp.response(204)
    def delete(self, allotment, membership):
        allotment_id = allotment.id
        keys = [
            key
            for m in db.session.query(Media).filter_by(allotment_id=allotment_id)
            for key in (m.storage_key, m.thumb_key)
        ]
        db.session.delete(allotment)
        db.session.commit()
        safe_delete(*keys)
        safe_delete_prefix(f"allotments/{allotment_id}/layers")
        events.emit("allotment.deleted", actor_id=membership.user_id, allotment_id=allotment_id)


@blp.route("/<int:allotment_id>/members")
class MemberList(MethodView):
    @require_role(Role.VIEWER)
    @blp.response(200, MemberSchema(many=True))
    def get(self, allotment, membership):
        return [_member(m) for m in allotment.memberships]

    @require_role(Role.OWNER)
    @blp.arguments(MemberAddSchema)
    @blp.response(201, MemberSchema)
    def post(self, data, allotment, membership):
        user = db.session.query(User).filter_by(email=data["email"].lower()).one_or_none()
        if user is None:
            abort(404, message="No user with that email")
        if (
            db.session.query(Membership)
            .filter_by(user_id=user.id, allotment_id=allotment.id)
            .first()
        ):
            abort(409, message="Already a member")
        new = Membership(user_id=user.id, allotment_id=allotment.id, role=data["role"])
        db.session.add(new)
        db.session.commit()
        events.emit(
            "member.added",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={"user_id": user.id},
            payload={"role": new.role},
        )
        return _member(new)


@blp.route("/<int:allotment_id>/members/<int:user_id>")
class MemberDetail(MethodView):
    def _target(self, allotment: Allotment, user_id: int) -> Membership:
        target = (
            db.session.query(Membership)
            .filter_by(user_id=user_id, allotment_id=allotment.id)
            .one_or_none()
        )
        if target is None:
            abort(404, message="Member not found")
        return target

    @require_role(Role.OWNER)
    @blp.arguments(MemberUpdateSchema)
    @blp.response(200, MemberSchema)
    def patch(self, data, allotment, membership, user_id):
        target = self._target(allotment, user_id)
        if target.role == Role.OWNER and data["role"] != Role.OWNER:
            if _owner_count(allotment.id) <= 1:
                abort(409, message="An allotment needs at least one owner")
        target.role = data["role"]
        db.session.commit()
        events.emit(
            "member.role_changed",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={"user_id": user_id},
            payload={"role": target.role},
        )
        return _member(target)

    @jwt_required()
    @blp.response(204)
    def delete(self, allotment_id, user_id):
        """Owners can remove anyone; any member can leave."""
        caller = current_user()
        allotment = db.session.get(Allotment, allotment_id)
        caller_m = (
            db.session.query(Membership)
            .filter_by(user_id=caller.id, allotment_id=allotment_id)
            .one_or_none()
        )
        if allotment is None or caller_m is None:
            abort(404, message="Allotment not found")
        if user_id != caller.id and caller_m.role != Role.OWNER:
            abort(403, message="Requires owner role")
        target = self._target(allotment, user_id)
        if target.role == Role.OWNER and _owner_count(allotment_id) <= 1:
            abort(409, message="An allotment needs at least one owner")
        db.session.delete(target)
        db.session.commit()
        events.emit(
            "member.removed",
            actor_id=caller.id,
            allotment_id=allotment_id,
            subject={"user_id": user_id},
        )
