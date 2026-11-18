"""Operations on whole allotments that more than one endpoint needs."""

from .extensions import db
from .models import Allotment, Media
from .storage import safe_delete, safe_delete_prefix


def collect_files(allotment_id: int) -> list[str]:
    """Storage keys of every media file (and thumbnail) in an allotment."""
    return [
        key
        for m in db.session.query(Media).filter_by(allotment_id=allotment_id)
        for key in (m.storage_key, m.thumb_key)
    ]


def stage_allotment_delete(allotment: Allotment) -> tuple[int, list[str]]:
    """Mark an allotment for deletion without committing; returns what to clean up afterwards."""
    allotment_id = allotment.id
    keys = collect_files(allotment_id)
    db.session.delete(allotment)
    return allotment_id, keys


def remove_allotment_files(allotment_id: int, keys: list[str]) -> None:
    """Delete an allotment's files from storage. Call after the database commit."""
    safe_delete(*keys)
    safe_delete_prefix(f"allotments/{allotment_id}/layers")
    safe_delete_prefix(f"allotments/{allotment_id}/stills")
