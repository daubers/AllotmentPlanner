"""Turns domain events into queued Mastodon posts (the event-bus subscribers live here)."""

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from flask import current_app
from sqlalchemy.orm.attributes import flag_modified

from .events import Event
from .extensions import db
from .models import MapFeature, MastodonAccount, MastodonPost

log = structlog.get_logger(__name__)

MAX_ATTACHMENTS = 4  # Mastodon's limit per status
HASHTAGS = "#allotment #growyourown"


def _now() -> datetime:
    return datetime.now(UTC)


def active_account(allotment_id: int, *, flag: str) -> MastodonAccount | None:
    account = db.session.query(MastodonAccount).filter_by(allotment_id=allotment_id).one_or_none()
    return account if account and account.enabled and getattr(account, flag) else None


def enqueue(post: MastodonPost, countdown: float = 0) -> None:
    from .tasks import send_mastodon_post

    send_mastodon_post.apply_async(args=[post.id], countdown=countdown)


def new_post(allotment_id: int, kind: str, text: str, **extra) -> MastodonPost:
    post = MastodonPost(
        allotment_id=allotment_id,
        kind=kind,
        text=text,
        idempotency_key=str(uuid.uuid4()),
        media_ids=extra.pop("media_ids", []),
        **extra,
    )
    db.session.add(post)
    return post


def on_task_completed(event: Event) -> None:
    if event.allotment_id is None or not active_account(
        event.allotment_id, flag="on_task_completed"
    ):
        return
    title = (event.payload.get("title") or "a job").strip()
    where = ""
    feature_id = event.subject.get("feature_id")
    feature = db.session.get(MapFeature, feature_id) if feature_id else None
    if feature and feature.name:
        where = f" ({feature.name})"
    post = new_post(event.allotment_id, "task", f"✅ Done: {title}{where}\n\n{HASHTAGS}")
    db.session.commit()
    enqueue(post)


def on_media_processed(event: Event) -> None:
    """Photos only. A burst of uploads is folded into one post (up to four pictures)."""
    if event.allotment_id is None or event.payload.get("kind") != "photo":
        return
    if not active_account(event.allotment_id, flag="on_photos"):
        return
    media_id = event.subject["media_id"]
    now = _now()
    collecting = (
        db.session.query(MastodonPost)
        .filter(
            MastodonPost.allotment_id == event.allotment_id,
            MastodonPost.kind == "photos",
            MastodonPost.status == "pending",
            MastodonPost.send_after > now,
        )
        .order_by(MastodonPost.id.desc())
        .first()
    )
    if collecting and len(collecting.media_ids) < MAX_ATTACHMENTS:
        collecting.media_ids = [*collecting.media_ids, media_id]
        collecting.text = photos_text(len(collecting.media_ids))
        flag_modified(collecting, "media_ids")
        db.session.commit()
        return
    delay = current_app.config["MASTODON_PHOTO_BATCH_SECONDS"]
    post = new_post(
        event.allotment_id,
        "photos",
        photos_text(1),
        media_ids=[media_id],
        send_after=now + timedelta(seconds=delay),
    )
    db.session.commit()
    enqueue(post, countdown=delay)


def photos_text(count: int) -> str:
    if count == 1:
        return f"📷 Progress on the plot\n\n{HASHTAGS}"
    return f"📷 {count} new photos from the plot\n\n{HASHTAGS}"


def digest_text(day: dict, streak: int) -> str | None:
    """'Today on the plot: ...' or None if nothing happened."""
    bits = []
    if day["tasks_done"]:
        bits.append(f"{day['tasks_done']} {'job' if day['tasks_done'] == 1 else 'jobs'} done")
    if day["photos_added"]:
        bits.append(f"{day['photos_added']} {'photo' if day['photos_added'] == 1 else 'photos'}")
    if day["map_edits"]:
        bits.append(f"{day['map_edits']} map {'edit' if day['map_edits'] == 1 else 'edits'}")
    if not bits:
        return None
    text = f"🌱 Today on the plot: {', '.join(bits)}."
    if streak > 1:
        text += f" {streak} days in a row!"
    return f"{text}\n\n{HASHTAGS}"


def register(events) -> None:
    events.subscribe("task.completed", on_task_completed)
    events.subscribe("media.processed", on_media_processed)
