"""Celery tasks. Imported by the worker via ``include=`` in celery_app."""

import os
import shutil
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import structlog
from flask import current_app, has_app_context

from . import events, media_meta
from . import mapping_geo as geo
from .celery_app import celery
from .crypto import decrypt
from .extensions import db
from .fediverse import MastodonClient, MastodonError
from .metrics import MASTODON_POSTS
from .models import (
    Allotment,
    LogEntry,
    MapJob,
    MastodonAccount,
    MastodonPost,
    Media,
    PacketScan,
    SeedPacket,
)
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
        if meta.taken_at and media.taken_at_source not in ("manual", "device"):
            media.taken_at, media.taken_at_source = meta.taken_at, "exif"
        if meta.lat is not None and media.lat is None:
            media.lat, media.lng, media.heading = meta.lat, meta.lng, meta.heading
            media.position_source = "exif"
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


MASTODON_MAX_ATTEMPTS = 5


def _backoff(attempts: int) -> int:
    return min(30 * 4**attempts, 1800)  # 30s, 2m, 8m, 32m (capped at 30m)


def _finish_post(post: MastodonPost, status: str, error: str | None = None, **fields) -> None:
    post.status, post.error = status, (error[:500] if error else None)
    for key, value in fields.items():
        setattr(post, key, value)
    db.session.commit()
    MASTODON_POSTS.labels(post.kind, status).inc()
    events.emit(
        "mastodon.posted" if status == "sent" else f"mastodon.{status}",
        allotment_id=post.allotment_id,
        subject={"post_id": post.id},
        payload={"kind": post.kind, "error": post.error},
    )


def _upload_photos(client, post: MastodonPost, storage, tmp: str) -> list[str]:
    remote_ids = []
    for index, media_id in enumerate(post.media_ids):
        media = db.session.get(Media, media_id)
        if media is None or media.kind != "photo":
            continue  # deleted since queueing: post the rest
        source, share = os.path.join(tmp, f"src{index}"), os.path.join(tmp, f"share{index}.jpg")
        storage.download(media.storage_key, source)
        media_meta.make_share_copy(source, share)
        remote_ids.append(
            client.upload_media(share, f"photo{index}.jpg", "image/jpeg", media.caption)
        )
    return remote_ids


@celery.task(name="allotment.send_mastodon_post")
def send_mastodon_post(post_id: int) -> str:
    """Send one queued post. Transient failures reschedule themselves with backoff."""
    with _app().app_context():
        # Claim the row so a duplicate delivery can't post twice.
        now = datetime.now(UTC)
        claimed = (
            db.session.query(MastodonPost)
            .filter(
                MastodonPost.id == post_id,
                MastodonPost.status == "pending",
                MastodonPost.send_after <= now + timedelta(seconds=1),
            )
            .update({"status": "sending"}, synchronize_session=False)
        )
        db.session.commit()
        if not claimed:
            return "skipped"
        post = db.session.get(MastodonPost, post_id)
        structlog.contextvars.bind_contextvars(post_id=post_id, allotment_id=post.allotment_id)
        account = (
            db.session.query(MastodonAccount)
            .filter_by(allotment_id=post.allotment_id)
            .one_or_none()
        )
        if account is None:
            _finish_post(post, "skipped", "Mastodon is no longer connected for this allotment")
            return "skipped"
        try:
            client = MastodonClient(account.instance_url, decrypt(account.token_encrypted))
            remote_ids: list[str] = []
            if post.media_ids:
                with tempfile.TemporaryDirectory() as tmp:
                    remote_ids = _upload_photos(client, post, get_storage(), tmp)
            visibility = "direct" if post.kind == "test" else account.visibility
            status = client.create_status(post.text, visibility, remote_ids, post.idempotency_key)
        except (MastodonError, ValueError) as exc:
            permanent = isinstance(exc, ValueError) or exc.permanent
            post.attempts += 1
            if permanent or post.attempts >= MASTODON_MAX_ATTEMPTS:
                log.warning("mastodon_post_failed", error=str(exc), attempts=post.attempts)
                _finish_post(post, "failed", str(exc))
                return "failed"
            delay = _backoff(post.attempts - 1)
            post.send_after = datetime.now(UTC) + timedelta(seconds=delay)
            _finish_post_retry(post, str(exc))
            send_mastodon_post.apply_async(args=[post_id], countdown=delay)
            return "retrying"
        except Exception as exc:  # noqa: BLE001 - never leave a row stuck in "sending"
            log.exception("mastodon_post_crashed")
            post.attempts += 1
            _finish_post(post, "failed", f"Unexpected error: {exc.__class__.__name__}")
            return "failed"
        post.attempts += 1
        log.info("mastodon_posted", kind=post.kind, media=len(remote_ids))
        _finish_post(post, "sent", None, remote_url=status.get("url"), posted_at=datetime.now(UTC))
        return "sent"


def _finish_post_retry(post: MastodonPost, error: str) -> None:
    post.status, post.error = "pending", error[:500]
    db.session.commit()
    MASTODON_POSTS.labels(post.kind, "retry").inc()
    log.warning("mastodon_post_retry", error=error, attempts=post.attempts)


@celery.task(name="allotment.mastodon_daily_digest")
def mastodon_daily_digest() -> int:
    """Once a day, post a summary for each allotment that opted in and did something today."""
    from .api.overview import build_overview
    from .mastodon_posts import digest_text, enqueue, new_post

    queued = 0
    with _app().app_context():
        today = datetime.now(UTC).date()
        accounts = (
            db.session.query(MastodonAccount).filter_by(enabled=True, daily_digest=True).all()
        )
        for account in accounts:
            already = (
                db.session.query(MastodonPost)
                .filter_by(allotment_id=account.allotment_id, kind="digest", digest_date=today)
                .first()
            )
            if already:
                continue
            allotment = db.session.get(Allotment, account.allotment_id)
            overview = build_overview(allotment, 7, today)
            text = digest_text(overview["days"][-1], overview["streak"]["current"])
            if text is None:
                continue
            post = new_post(account.allotment_id, "digest", text, digest_date=today)
            db.session.commit()
            enqueue(post)
            queued += 1
    return queued


@celery.task(name="allotment.mastodon_sweep")
def mastodon_sweep() -> int:
    """Safety net: re-queue posts whose delayed task was lost (e.g. a Redis flush) or whose
    worker died mid-send."""
    with _app().app_context():
        now = datetime.now(UTC)
        stuck = (
            db.session.query(MastodonPost)
            .filter(
                (
                    (MastodonPost.status == "pending")
                    & (MastodonPost.send_after < now - timedelta(minutes=5))
                )
                | (
                    (MastodonPost.status == "sending")
                    & (MastodonPost.created_at < now - timedelta(minutes=15))
                    & (MastodonPost.send_after < now - timedelta(minutes=15))
                )
            )
            .all()
        )
        for post in stuck:
            post.status = "pending"
            db.session.commit()
            send_mastodon_post.apply_async(args=[post.id])
        return len(stuck)


def _work_root() -> Path:
    return Path(os.environ.get("MAPPING_WORK_DIR") or tempfile.gettempdir())


@celery.task(name="allotment.run_map_job")
def run_map_job(job_id: int) -> str:
    """Build a map layer from photos. Slow, so it runs on the ``mapping`` queue (``mapper``)."""
    from . import mapping_pipeline as pipeline

    with _app().app_context():
        job = db.session.get(MapJob, job_id)
        if job is None or job.status != "queued":
            return "skipped"
        structlog.contextvars.bind_contextvars(map_job_id=job_id, allotment_id=job.allotment_id)

        def finish(status: str, error: str | None = None) -> str:
            job.status, job.error = status, (error[:500] if error else None)
            job.finished_at = datetime.now(UTC)
            db.session.commit()
            events.emit(
                f"map_job.{status}",
                actor_id=job.created_by,
                allotment_id=job.allotment_id,
                subject={"map_job_id": job.id},
                payload={"error": job.error, "objects": job.objects_found},
            )
            return status

        if job.cancel_requested:
            return finish("cancelled")
        job.status, job.started_at = "running", datetime.now(UTC)
        db.session.commit()
        work = _work_root() / f"job-{job_id}"
        shutil.rmtree(work, ignore_errors=True)
        work.mkdir(parents=True)
        try:
            layer = pipeline.process(job, work)
            db.session.commit()
            if layer is not None:
                events.emit(
                    "layer.created",
                    actor_id=job.created_by,
                    allotment_id=job.allotment_id,
                    subject={"layer_id": layer.id, "map_job_id": job.id},
                    payload={"tiles": layer.tile_count},
                )
            log.info("map_job_done", objects=job.objects_found, overlay=layer is not None)
            return finish("ready")
        except pipeline.JobCancelled:
            db.session.rollback()
            return finish("cancelled")
        except (pipeline.JobFailed, geo.ReconstructionError) as exc:
            db.session.rollback()
            log.warning("map_job_failed", error=str(exc))
            return finish("failed", str(exc))
        except Exception as exc:  # noqa: BLE001 - record any failure on the job, then re-log
            db.session.rollback()
            log.exception("map_job_crashed")
            return finish("failed", f"Unexpected error: {exc.__class__.__name__}")
        finally:
            if not os.environ.get(
                "MAPPING_KEEP_WORK"
            ):  # set it to inspect a run's files afterwards
                shutil.rmtree(work, ignore_errors=True)


def _save_crop(scan: PacketScan, crop) -> Media:
    """Keep the calendar as read as a photo of the packet, so the review screen can show it."""
    import io
    import uuid

    buf = io.BytesIO()
    crop.convert("RGB").save(buf, "JPEG", quality=88)
    key = f"allotments/{scan.allotment_id}/{uuid.uuid4().hex}.jpg"
    with tempfile.NamedTemporaryFile(suffix=".jpg") as f:
        f.write(buf.getvalue())
        f.flush()
        get_storage().put(key, f.name, "image/jpeg")
    media = Media(
        allotment_id=scan.allotment_id,
        uploaded_by=scan.created_by,
        kind="photo",
        filename="calendar.jpg",
        content_type="image/jpeg",
        size_bytes=len(buf.getvalue()),
        storage_key=key,
        thumb_key=key,  # small already
        width=crop.width,
        height=crop.height,
        caption="Calendar as read from the packet",
        status="ready",
    )
    db.session.add(media)
    db.session.flush()
    return media


@celery.task(name="allotment.run_packet_scan")
def run_packet_scan(scan_id: int) -> str:
    """Read a packet photo into a draft packet. CPU only; runs on the ``vision`` queue."""
    from PIL import Image, ImageOps

    from . import packet_scan

    with _app().app_context():
        scan = db.session.get(PacketScan, scan_id)
        if scan is None or scan.status != "queued":
            return "skipped"
        structlog.contextvars.bind_contextvars(
            packet_scan_id=scan_id, allotment_id=scan.allotment_id
        )
        scan.status, scan.started_at = "running", datetime.now(UTC)
        db.session.commit()

        def fail(message: str) -> str:
            db.session.rollback()
            scan.status, scan.error = "failed", message[:500]
            scan.finished_at = datetime.now(UTC)
            db.session.commit()
            return "failed"

        media = db.session.get(Media, scan.media_id) if scan.media_id else None
        if media is None:
            return fail("The photo is gone")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, "photo")
                get_storage().download(media.storage_key, path)
                with Image.open(path) as opened:
                    image = ImageOps.exif_transpose(opened).convert("RGB")
            result = packet_scan.scan(image)
            facts = result.facts
            packet = SeedPacket(
                allotment_id=scan.allotment_id,
                created_by=scan.created_by,
                status="draft",
                name=(result.name or "Unnamed packet")[:200],
                variety=(result.variety or "")[:200],
                supplier=facts.supplier or "",
                sow_depth_mm=facts.sow_depth_mm,
                germinate_days_min=facts.germinate_days_min,
                germinate_days_max=facts.germinate_days_max,
                best_before_year=facts.best_before_year,
                seeds_in_packet=facts.seeds_in_packet,
                raw_text=result.raw_text[:20000],
                calendar=result.calendar or {},
            )
            db.session.add(packet)
            db.session.flush()
            media.packet_id = packet.id
            if result.calendar_crop is not None:
                crop = _save_crop(scan, result.calendar_crop)
                crop.packet_id = packet.id
                scan.crop_media_id = crop.id
            scan.packet_id = packet.id
            scan.calendar_source = result.calendar_source
            scan.rotation = result.rotation
            scan.missing = result.missing
            scan.status, scan.finished_at = "ready", datetime.now(UTC)
            db.session.commit()
        except Exception as exc:  # noqa: BLE001 - record any failure on the scan
            log.exception("packet_scan_failed")
            return fail(f"Could not read the photo: {exc.__class__.__name__}")
        events.emit(
            "packet.scanned",
            actor_id=scan.created_by,
            allotment_id=scan.allotment_id,
            subject={"packet_id": packet.id, "packet_scan_id": scan.id},
            payload={"missing": scan.missing, "calendar": scan.calendar_source},
        )
        return "ready"


@celery.task(name="allotment.prune_logs")
def prune_logs() -> int:
    """Drop log lines older than LOG_RETENTION_DAYS (the admin page's log table)."""
    with _app().app_context():
        days = current_app.config["LOG_RETENTION_DAYS"]
        cutoff = datetime.now(UTC) - timedelta(days=days)
        removed = LogEntry.query.filter(LogEntry.at < cutoff).delete()
        db.session.commit()
        return removed
