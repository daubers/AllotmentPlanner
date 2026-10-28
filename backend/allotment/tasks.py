"""Celery tasks. Imported by the worker via ``include=`` in celery_app."""

import os
import tempfile

import structlog
from flask import current_app, has_app_context

from . import events, media_meta
from .celery_app import celery
from .extensions import db
from .models import Media
from .storage import get_storage

log = structlog.get_logger(__name__)
_worker_app = None


def _app():
    """The Flask app: the current one when running eagerly, otherwise one built for the worker."""
    global _worker_app
    if has_app_context():
        return current_app._get_current_object()
    if _worker_app is None:
        from . import create_app

        _worker_app = create_app()
    return _worker_app


def _fail(media: Media, message: str) -> str:
    media.status = "failed"
    media.error = message[:500]
    db.session.commit()
    events.emit(
        "media.failed",
        actor_id=media.uploaded_by,
        allotment_id=media.allotment_id,
        subject={"media_id": media.id},
        payload={"error": media.error},
    )
    return "failed"


@celery.task(name="allotment.process_media")
def process_media(media_id: int) -> str:
    """Read EXIF/ffprobe metadata and make a thumbnail for an uploaded file."""
    with _app().app_context():
        media = db.session.get(Media, media_id)
        if media is None:
            return "missing"
        structlog.contextvars.bind_contextvars(media_id=media_id)
        storage = get_storage()
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "source")
            thumb = os.path.join(tmp, "thumb.jpg")
            try:
                storage.download(media.storage_key, source)
                if media.kind == "photo":
                    meta = media_meta.read_photo(source)
                    media_meta.make_photo_thumbnail(source, thumb)
                else:
                    if not media_meta.have_ffmpeg():
                        return _fail(media, "ffmpeg is not installed on this worker")
                    meta = media_meta.read_video(source)
                    try:
                        media_meta.make_video_thumbnail(source, thumb, meta.duration_s)
                    except Exception:  # noqa: BLE001 - a missing thumbnail must not fail the upload
                        log.warning("video_thumbnail_failed", exc_info=True)
                has_thumb = os.path.exists(thumb)
                thumb_key = f"allotments/{media.allotment_id}/thumbs/{media.id}.jpg"
                if has_thumb:
                    storage.put(thumb_key, thumb, "image/jpeg")
            except media_meta.UnsupportedMedia as exc:
                return _fail(media, str(exc))
            except Exception as exc:  # noqa: BLE001 - record any failure on the row, then re-log
                log.exception("process_media_failed")
                return _fail(media, f"Processing failed: {exc.__class__.__name__}")

        media.width, media.height, media.duration_s = meta.width, meta.height, meta.duration_s
        if meta.taken_at and media.taken_at_source != "manual":
            media.taken_at, media.taken_at_source = meta.taken_at, "exif"
        if meta.lat is not None and media.lat is None:
            media.lat, media.lng, media.heading = meta.lat, meta.lng, meta.heading
        elif meta.heading is not None and media.heading is None:
            media.heading = meta.heading
        media.thumb_key = thumb_key if has_thumb else None
        media.status, media.error = "ready", None
        db.session.commit()
        log.info("media_processed", kind=media.kind, has_gps=media.lat is not None)
        events.emit(
            "media.processed",
            actor_id=media.uploaded_by,
            allotment_id=media.allotment_id,
            subject={"media_id": media.id},
            payload={"has_gps": media.lat is not None, "kind": media.kind},
        )
        return "ready"
