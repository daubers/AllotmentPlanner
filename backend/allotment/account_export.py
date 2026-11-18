"""Build a person's data export: a zip with their data as JSON and the files they uploaded.

It holds what is theirs: their profile, how they sign in, their memberships, and every row that
names them as its author (created, uploaded, assigned, completed, measured, or the actor in the
activity log), plus the photos and videos they uploaded. Other people's content in a shared
allotment is not included, and neither are secrets such as password hashes or the Mastodon token.
"""

import json
import os
import re
import tempfile
import zipfile
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from flask import current_app
from geoalchemy2.elements import WKBElement
from geoalchemy2.shape import to_shape
from sqlalchemy import or_, select

from .extensions import db
from .models import AccountExport, Media, OidcIdentity, User
from .storage import get_storage

# Tables that point at users but are about signing in or the export itself, not their content.
_SKIP_TABLES = {"oidc_identities", "oidc_login_codes", "memberships", "account_exports"}
# Columns that are storage paths: the zip carries the file, so the path means nothing to the reader.
_SKIP_COLUMNS = {"storage_key", "thumb_key"}


def _plain(value):
    """A JSON-safe version of a database value."""
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, WKBElement):
        return to_shape(value).__geo_interface__
    if isinstance(value, bytes | memoryview):
        return None
    return value


def _authored_tables():
    """(table, [columns naming a user]) for every table that records who did something."""
    found = []
    for table in db.metadata.sorted_tables:
        if table.name in _SKIP_TABLES:
            continue
        cols = [
            c
            for c in table.columns
            if any(fk.target_fullname == "users.id" for fk in c.foreign_keys)
        ]
        if cols:
            found.append((table, cols))
    return found


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name or "file")[:80] or "file"


def collect(user: User) -> tuple[dict, list[Media]]:
    """The export's JSON, and the media rows whose files go in the zip."""
    data: dict = {
        "exported_at": datetime.now(UTC).isoformat(),
        "profile": {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "created_at": user.created_at.isoformat(),
            "has_password": bool(user.password_hash),
        },
        "sign_in_providers": [
            {"provider": i.provider, "email": i.email, "linked_at": i.created_at.isoformat()}
            for i in db.session.query(OidcIdentity).filter_by(user_id=user.id)
        ],
        "memberships": [
            {"allotment_id": m.allotment_id, "allotment": m.allotment.name, "role": m.role}
            for m in user.memberships
        ],
        "content": {},
    }
    for table, cols in _authored_tables():
        rows = db.session.execute(
            select(table).where(or_(*[c == user.id for c in cols])).order_by(table.c.id)
        ).mappings()
        out = [{k: _plain(v) for k, v in row.items() if k not in _SKIP_COLUMNS} for row in rows]
        if out:
            data["content"][table.name] = out
    media = db.session.query(Media).filter_by(uploaded_by=user.id).order_by(Media.id).all()
    for item in data["content"].get("media", []):
        row = next(m for m in media if m.id == item["id"])
        item["file"] = f"media/{row.id}_{_safe_name(row.filename)}"
    return data, media


def build(export: AccountExport) -> None:
    """Write the zip to storage and mark the export ready (or failed)."""
    user = db.session.get(User, export.user_id)
    if user is None:
        return
    storage = get_storage()
    fd, path = tempfile.mkstemp(suffix=".zip")
    os.close(fd)
    try:
        data, media = collect(user)
        missing = []
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            for m in media:
                fd2, tmp = tempfile.mkstemp()
                os.close(fd2)
                try:
                    storage.download(m.storage_key, tmp)
                    zf.write(tmp, f"media/{m.id}_{_safe_name(m.filename)}")
                except Exception:  # noqa: BLE001 - a lost file must not sink the whole export
                    missing.append(m.id)
                finally:
                    os.unlink(tmp)
            if missing:
                data["missing_media_ids"] = missing
            zf.writestr("data.json", json.dumps(data, indent=2, ensure_ascii=False))
        key = f"exports/{user.id}/{export.id}.zip"
        storage.put(key, path, "application/zip")
        export.storage_key = key
        export.size_bytes = os.path.getsize(path)
        export.status = "ready"
        export.expires_at = datetime.now(UTC) + timedelta(
            hours=current_app.config["ACCOUNT_EXPORT_TTL_HOURS"]
        )
    except Exception as exc:  # noqa: BLE001 - recorded so the person is told, then re-raised
        db.session.rollback()
        export = db.session.get(AccountExport, export.id)
        export.status = "failed"
        export.error = f"{exc.__class__.__name__}: {exc}"[:500]
        db.session.commit()
        raise
    finally:
        os.unlink(path)
    db.session.commit()
