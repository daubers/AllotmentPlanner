from datetime import UTC, datetime

from flask.views import MethodView
from flask_smorest import Blueprint, abort

from .. import events
from ..extensions import db
from ..models import FeatureNote, MapFeature, Role, User
from ..schemas import (
    FeatureNoteInSchema,
    FeatureNotePatchSchema,
    FeatureNoteQuerySchema,
    FeatureNoteSchema,
)
from ..security import require_role

blp = Blueprint(
    "notes",
    __name__,
    url_prefix="/api/v1/allotments/<int:allotment_id>/notes",
    description="Dated notes on map features, any number a day",
)


def _aware(when: datetime) -> datetime:
    return when if when.tzinfo else when.replace(tzinfo=UTC)


def _get(allotment, note_id: int) -> FeatureNote:
    note = db.session.get(FeatureNote, note_id)
    if note is None or note.allotment_id != allotment.id:
        abort(404, message="Note not found")
    return note


def _feature(allotment, feature_id: int) -> MapFeature:
    feature = db.session.get(MapFeature, feature_id)
    if feature is None or feature.allotment_id != allotment.id:
        abort(422, message="feature_id does not belong to this allotment")
    return feature


def note_to_dict(note: FeatureNote) -> dict:
    feature = db.session.get(MapFeature, note.feature_id)
    author = db.session.get(User, note.created_by) if note.created_by else None
    return {
        "id": note.id,
        "feature_id": note.feature_id,
        "feature_name": ((feature.name if feature else "") or f"Feature {note.feature_id}"),
        "body": note.body,
        "noted_at": note.noted_at,
        "author": author.display_name if author else None,
        "created_at": note.created_at,
        "updated_at": note.updated_at,
    }


@blp.route("")
class Notes(MethodView):
    @require_role(Role.VIEWER)
    @blp.arguments(FeatureNoteQuerySchema, location="query")
    @blp.response(200, FeatureNoteSchema(many=True))
    def get(self, args, allotment, membership):
        """Notes, newest first; `feature_id` narrows to one feature."""
        query = db.session.query(FeatureNote).filter_by(allotment_id=allotment.id)
        if "feature_id" in args:
            query = query.filter_by(feature_id=args["feature_id"])
        notes = query.order_by(FeatureNote.noted_at.desc(), FeatureNote.id.desc()).all()
        return [note_to_dict(n) for n in notes]

    @require_role(Role.EDITOR)
    @blp.arguments(FeatureNoteInSchema)
    @blp.response(201, FeatureNoteSchema)
    def post(self, data, allotment, membership):
        """Add a note to a feature."""
        feature = _feature(allotment, data["feature_id"])
        note = FeatureNote(
            allotment_id=allotment.id,
            feature_id=feature.id,
            body=data["body"].strip(),
            noted_at=_aware(data["noted_at"]) if data["noted_at"] else datetime.now(UTC),
            created_by=membership.user_id,
        )
        db.session.add(note)
        db.session.commit()
        events.emit(
            "note.created",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={"note_id": note.id, "feature_id": feature.id},
            payload={},
        )
        return note_to_dict(note)


@blp.route("/<int:note_id>")
class NoteView(MethodView):
    @require_role(Role.EDITOR)
    @blp.arguments(FeatureNotePatchSchema)
    @blp.response(200, FeatureNoteSchema)
    def patch(self, data, allotment, membership, note_id):
        """Change a note's text or the time it is about."""
        note = _get(allotment, note_id)
        if "body" in data:
            note.body = data["body"].strip()
        if "noted_at" in data:
            note.noted_at = _aware(data["noted_at"])
        db.session.commit()
        events.emit(
            "note.updated",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={"note_id": note.id, "feature_id": note.feature_id},
            payload={},
        )
        return note_to_dict(note)

    @require_role(Role.EDITOR)
    @blp.response(204)
    def delete(self, allotment, membership, note_id):
        """Delete a note."""
        note = _get(allotment, note_id)
        subject = {"note_id": note.id, "feature_id": note.feature_id}
        db.session.delete(note)
        db.session.commit()
        events.emit(
            "note.deleted",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject=subject,
            payload={},
        )
