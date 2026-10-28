import mimetypes
import os
import re
import tempfile
import uuid
from datetime import UTC, datetime, time, timedelta

from flask import Response, current_app, request
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from itsdangerous import BadSignature, URLSafeTimedSerializer
from werkzeug.utils import secure_filename

from .. import events, media_meta
from ..celery_app import celery
from ..extensions import db
from ..models import MapFeature, Media, Role, Task
from ..schemas import (
    MediaPatchSchema,
    MediaQuerySchema,
    MediaSchema,
    MediaUploadFormSchema,
)
from ..security import require_role
from ..storage import get_storage, safe_delete
from ..tasks import process_media

blp = Blueprint(
    "media",
    __name__,
    url_prefix="/api/v1/allotments/<int:allotment_id>/media",
    description="Photos and videos",
)
files_blp = Blueprint(
    "media-files", __name__, url_prefix="/api/v1/media", description="Signed media downloads"
)


def _signer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["JWT_SECRET_KEY"], salt="media-url")


def media_to_dict(m: Media) -> dict:
    """JSON for a media row. File links are signed: <img>/<video> can't send a bearer token."""
    token = _signer().dumps(m.id)
    return {
        "id": m.id,
        "kind": m.kind,
        "filename": m.filename,
        "content_type": m.content_type,
        "size_bytes": m.size_bytes,
        "width": m.width,
        "height": m.height,
        "duration_s": m.duration_s,
        "taken_at": m.taken_at,
        "taken_at_source": m.taken_at_source,
        "lat": m.lat,
        "lng": m.lng,
        "heading": m.heading,
        "feature_id": m.feature_id,
        "task_id": m.task_id,
        "caption": m.caption,
        "status": m.status,
        "error": m.error,
        "url": f"/api/v1/media/{m.id}/file?t={token}",
        "thumb_url": f"/api/v1/media/{m.id}/thumb?t={token}" if m.thumb_key else None,
        "uploaded_by": m.uploaded_by,
        "created_at": m.created_at,
    }


def _check_refs(allotment, feature_id, task_id) -> None:
    if feature_id is not None:
        feature = db.session.get(MapFeature, feature_id)
        if feature is None or feature.allotment_id != allotment.id:
            abort(422, message="feature_id does not belong to this allotment")
    if task_id is not None:
        task = db.session.get(Task, task_id)
        if task is None or task.allotment_id != allotment.id:
            abort(422, message="task_id does not belong to this allotment")


def _get(allotment, media_id: int) -> Media:
    media = db.session.get(Media, media_id)
    if media is None or media.allotment_id != allotment.id:
        abort(404, message="Media not found")
    return media


def _enqueue(media: Media) -> None:
    try:
        process_media.delay(media.id)
    except Exception:  # noqa: BLE001 - e.g. broker down: leave it pending, retry via /reprocess
        current_app.logger.exception("could not queue media processing")
    if celery.conf.task_always_eager:
        db.session.expire_all()  # the eager task committed through its own session


@blp.route("")
class MediaList(MethodView):
    @require_role(Role.VIEWER)
    @blp.arguments(MediaQuerySchema, location="query")
    @blp.response(200, MediaSchema(many=True))
    def get(self, args, allotment, membership):
        q = db.session.query(Media).filter_by(allotment_id=allotment.id)
        for key in ("kind", "feature_id", "task_id"):
            if key in args:
                q = q.filter(getattr(Media, key) == args[key])
        if "taken_from" in args:
            q = q.filter(Media.taken_at >= datetime.combine(args["taken_from"], time.min, UTC))
        if "taken_to" in args:
            q = q.filter(
                Media.taken_at
                < datetime.combine(args["taken_to"], time.min, UTC) + timedelta(days=1)
            )
        order = Media.taken_at.asc() if args["order"] == "asc" else Media.taken_at.desc()
        rows = q.order_by(order, Media.id).offset(args["offset"]).limit(args["limit"]).all()
        return [media_to_dict(m) for m in rows]

    @require_role(Role.EDITOR)
    @blp.arguments(MediaUploadFormSchema, location="form", content_type="multipart/form-data")
    @blp.response(201, MediaSchema)
    def post(self, form, allotment, membership):
        """Upload a photo or video. Time, GPS, size and thumbnail are read in the background."""
        _check_refs(allotment, form["feature_id"], form["task_id"])
        upload = request.files.get("file")
        if upload is None:
            abort(422, message="Missing 'file' in the multipart form")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "upload")
            upload.save(path)
            upload.close()  # drops the multipart spool now, not at the end of the request
            size = os.path.getsize(path)
            if size == 0:
                abort(422, message="The file is empty")
            with open(path, "rb") as f:
                head = f.read(32)
            try:
                kind = media_meta.sniff_kind(head)
            except media_meta.UnsupportedMedia as exc:
                abort(415, message=str(exc))
            ext = media_meta.extension_for(kind, head)
            content_type = mimetypes.types_map.get(ext, "application/octet-stream")
            key = f"allotments/{allotment.id}/{uuid.uuid4().hex}{ext}"
            get_storage().put(key, path, content_type)
        media = Media(
            allotment_id=allotment.id,
            uploaded_by=membership.user_id,
            kind=kind,
            filename=(secure_filename(upload.filename or "") or f"upload{ext}")[:255],
            content_type=content_type,
            size_bytes=size,
            storage_key=key,
            feature_id=form["feature_id"],
            task_id=form["task_id"],
            caption=form["caption"],
        )
        db.session.add(media)
        db.session.commit()
        events.emit(
            "media.uploaded",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={
                "media_id": media.id,
                "feature_id": media.feature_id,
                "task_id": media.task_id,
            },
            payload={"kind": kind, "size_bytes": size},
        )
        _enqueue(media)
        return media_to_dict(media)


@blp.route("/<int:media_id>")
class MediaDetail(MethodView):
    @require_role(Role.VIEWER)
    @blp.response(200, MediaSchema)
    def get(self, allotment, membership, media_id):
        return media_to_dict(_get(allotment, media_id))

    @require_role(Role.EDITOR)
    @blp.arguments(MediaPatchSchema)
    @blp.response(200, MediaSchema)
    def patch(self, data, allotment, membership, media_id):
        media = _get(allotment, media_id)
        _check_refs(allotment, data.get("feature_id"), data.get("task_id"))
        if ("lat" in data) != ("lng" in data) or (data.get("lat") is None) != (
            data.get("lng") is None
        ):
            abort(422, message="lat and lng must be set together (or both cleared)")
        for key in ("caption", "feature_id", "task_id", "lat", "lng", "heading"):
            if key in data:
                setattr(media, key, data[key])
        if "taken_at" in data:
            taken = data["taken_at"]
            media.taken_at = taken if taken.tzinfo else taken.replace(tzinfo=UTC)
            media.taken_at_source = "manual"
        db.session.commit()
        events.emit(
            "media.updated",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={"media_id": media.id},
            payload={"fields": sorted(data)},
        )
        return media_to_dict(media)

    @require_role(Role.EDITOR)
    @blp.response(204)
    def delete(self, allotment, membership, media_id):
        media = _get(allotment, media_id)
        keys = (media.storage_key, media.thumb_key)
        db.session.delete(media)
        db.session.commit()
        safe_delete(*keys)
        events.emit(
            "media.deleted",
            actor_id=membership.user_id,
            allotment_id=allotment.id,
            subject={"media_id": media_id},
        )


@blp.route("/<int:media_id>/reprocess")
class MediaReprocess(MethodView):
    @require_role(Role.EDITOR)
    @blp.response(200, MediaSchema)
    def post(self, allotment, membership, media_id):
        """Queue processing again, e.g. after a failure or if the broker was down at upload."""
        media = _get(allotment, media_id)
        media.status, media.error = "pending", None
        db.session.commit()
        _enqueue(media)
        return media_to_dict(media)


_RANGE = re.compile(r"bytes=(\d*)-(\d*)")


def _serve(key: str, content_type: str, filename: str) -> Response:
    storage = get_storage()
    size = storage.size(key)
    start, end, status = 0, size - 1, 200
    header = request.headers.get("Range")
    if header and size:
        match = _RANGE.fullmatch(header.strip())
        if not match or not (match[1] or match[2]):
            return Response(status=416, headers={"Content-Range": f"bytes */{size}"})
        if match[1]:
            start = int(match[1])
            end = min(int(match[2]), size - 1) if match[2] else size - 1
        else:  # "bytes=-N": the last N bytes
            start = max(size - int(match[2]), 0)
        if start > end or start >= size:
            return Response(status=416, headers={"Content-Range": f"bytes */{size}"})
        status = 206
    body = storage.read_range(key, start, end) if size else iter(())
    response = Response(body, status=status, mimetype=content_type, direct_passthrough=True)
    response.headers["Content-Length"] = str(max(end - start + 1, 0))
    response.headers["Accept-Ranges"] = "bytes"
    response.headers["Cache-Control"] = "private, max-age=3000"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Disposition"] = f'inline; filename="{filename}"'
    if status == 206:
        response.headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    return response


@files_blp.route("/<int:media_id>/<any(file,thumb):variant>")
class MediaFile(MethodView):
    @files_blp.doc(
        parameters=[{"in": "query", "name": "t", "required": True, "schema": {"type": "string"}}]
    )
    @files_blp.response(200)
    def get(self, media_id, variant):
        """The file or its thumbnail. Authorised by the signed ``t`` token from the media JSON."""
        try:
            token_id = _signer().loads(
                request.args.get("t", ""), max_age=current_app.config["MEDIA_URL_TTL_SECONDS"]
            )
        except BadSignature:
            abort(403, message="Invalid or expired link")
        media = db.session.get(Media, media_id)
        if media is None or token_id != media_id:
            abort(404, message="Media not found")
        if variant == "thumb":
            if not media.thumb_key:
                abort(404, message="No thumbnail")
            return _serve(media.thumb_key, "image/jpeg", f"thumb-{media.id}.jpg")
        return _serve(media.storage_key, media.content_type, media.filename)
