import enum
from datetime import UTC, date, datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .extensions import db


def _now() -> datetime:
    return datetime.now(UTC)


class Role(enum.StrEnum):
    VIEWER = "viewer"
    EDITOR = "editor"
    OWNER = "owner"

    @property
    def rank(self) -> int:
        return list(Role).index(self)


class User(db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Allotment(db.Model):
    __tablename__ = "allotments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="allotment", cascade="all, delete-orphan"
    )


class Membership(db.Model):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "allotment_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    allotment_id: Mapped[int] = mapped_column(
        ForeignKey("allotments.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    user: Mapped[User] = relationship(back_populates="memberships")
    allotment: Mapped[Allotment] = relationship(back_populates="memberships")


class FeatureKind(enum.StrEnum):
    BED = "bed"
    PATH = "path"
    SHED = "shed"
    TREE = "tree"
    WATER = "water"
    COMPOST = "compost"
    BOUNDARY = "boundary"
    OTHER = "other"


class MapFeature(db.Model):
    """A drawn object on the allotment map. Circles are a Point plus ``radius_m``."""

    __tablename__ = "map_features"

    id: Mapped[int] = mapped_column(primary_key=True)
    allotment_id: Mapped[int] = mapped_column(
        ForeignKey("allotments.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(20), default=FeatureKind.OTHER)
    name: Mapped[str] = mapped_column(String(120), default="")
    geometry = mapped_column(Geometry("GEOMETRY", srid=4326), nullable=False)
    radius_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    style: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class TaskStatus(enum.StrEnum):
    TODO = "todo"
    DOING = "doing"
    DONE = "done"


class Task(db.Model):
    """A job to do. Optionally pinned to a map feature and/or a point on the map."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    allotment_id: Mapped[int] = mapped_column(
        ForeignKey("allotments.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(10), default=TaskStatus.TODO, index=True)
    priority: Mapped[str] = mapped_column(String(10), default="normal")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    recurrence: Mapped[str | None] = mapped_column(String(10), nullable=True)
    assignee_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    feature_id: Mapped[int | None] = mapped_column(
        ForeignKey("map_features.id", ondelete="SET NULL"), nullable=True, index=True
    )
    location = mapped_column(Geometry("POINT", srid=4326), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class Media(db.Model):
    """An uploaded photo or video, with the metadata pulled from the file itself."""

    __tablename__ = "media"
    __table_args__ = (UniqueConstraint("allotment_id", "client_id", name="uq_media_client_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    allotment_id: Mapped[int] = mapped_column(
        ForeignKey("allotments.id", ondelete="CASCADE"), index=True
    )
    uploaded_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(10))  # photo | video
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(default=0)
    storage_key: Mapped[str] = mapped_column(String(300))
    thumb_key: Mapped[str | None] = mapped_column(String(300), nullable=True)
    width: Mapped[int | None] = mapped_column(nullable=True)
    height: Mapped[int | None] = mapped_column(nullable=True)
    duration_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, default=_now)
    taken_at_source: Mapped[str] = mapped_column(
        String(10), default="upload"
    )  # exif | upload | manual
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    heading: Mapped[float | None] = mapped_column(Float, nullable=True)
    position_source: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )  # where lat/lng came from: exif | device (the app's own GPS) | manual
    capture_session: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    client_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # the app's id for this upload, so a resent upload is recognised
    feature_id: Mapped[int | None] = mapped_column(
        ForeignKey("map_features.id", ondelete="SET NULL"), nullable=True, index=True
    )
    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    caption: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(10), default="pending")  # pending | ready | failed
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ActivityLog(db.Model):
    """A domain event worth remembering; feeds the progress overview and later Mastodon."""

    __tablename__ = "activity_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    allotment_id: Mapped[int] = mapped_column(
        ForeignKey("allotments.id", ondelete="CASCADE"), index=True
    )
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    type: Mapped[str] = mapped_column(String(40), index=True)
    subject: Mapped[dict] = mapped_column(JSON, default=dict)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, default=_now)


class MastodonAccount(db.Model):
    """The Mastodon account an allotment posts to. The token is stored encrypted."""

    __tablename__ = "mastodon_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    allotment_id: Mapped[int] = mapped_column(
        ForeignKey("allotments.id", ondelete="CASCADE"), unique=True
    )
    instance_url: Mapped[str] = mapped_column(String(300))
    token_encrypted: Mapped[str] = mapped_column(Text)
    handle: Mapped[str | None] = mapped_column(String(300), nullable=True)
    visibility: Mapped[str] = mapped_column(String(10), default="unlisted")
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    on_task_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    on_photos: Mapped[bool] = mapped_column(Boolean, default=False)
    daily_digest: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class MastodonPost(db.Model):
    """An outgoing status: queued, sent or failed, with the error so it can be retried."""

    __tablename__ = "mastodon_posts"
    __table_args__ = (UniqueConstraint("allotment_id", "kind", "digest_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    allotment_id: Mapped[int] = mapped_column(
        ForeignKey("allotments.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(10))  # task | photos | digest | test
    text: Mapped[str] = mapped_column(Text)
    media_ids: Mapped[list] = mapped_column(JSON, default=list)  # our Media ids, not Mastodon's
    digest_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(10), default="pending", index=True
    )  # pending | sending | sent | failed | skipped
    attempts: Mapped[int] = mapped_column(default=0)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    remote_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(36))
    send_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MapJob(db.Model):
    """A request to build a georeferenced map layer from photos and video (OpenSfM + GDAL)."""

    __tablename__ = "map_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    allotment_id: Mapped[int] = mapped_column(
        ForeignKey("allotments.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(
        String(10), default="queued", index=True
    )  # queued | running | ready | failed | cancelled
    stage: Mapped[str] = mapped_column(String(20), default="")
    media_ids: Mapped[list] = mapped_column(JSON, default=list)
    view: Mapped[str] = mapped_column(String(10), default="oblique")  # oblique | overhead
    camera_height_m: Mapped[float] = mapped_column(Float, default=1.7)
    # What to produce: recognised objects (suggestions to review) and/or the stitched photo overlay.
    detect_objects: Mapped[bool] = mapped_column(Boolean, default=True, server_default="false")
    overlay: Mapped[bool] = mapped_column(Boolean, default=False, server_default="true")
    objects_found: Mapped[int | None] = mapped_column(nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    log: Mapped[str] = mapped_column(Text, default="")
    shots_total: Mapped[int | None] = mapped_column(nullable=True)
    shots_used: Mapped[int | None] = mapped_column(nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MapLayer(db.Model):
    """A generated orthophoto, stored as XYZ tiles and shown over the map."""

    __tablename__ = "map_layers"

    id: Mapped[int] = mapped_column(primary_key=True)
    allotment_id: Mapped[int] = mapped_column(
        ForeignKey("allotments.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[int | None] = mapped_column(
        ForeignKey("map_jobs.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(120))
    west: Mapped[float] = mapped_column(Float)
    south: Mapped[float] = mapped_column(Float)
    east: Mapped[float] = mapped_column(Float)
    north: Mapped[float] = mapped_column(Float)
    min_zoom: Mapped[int] = mapped_column()
    max_zoom: Mapped[int] = mapped_column()
    tile_count: Mapped[int] = mapped_column(default=0)
    opacity: Mapped[float] = mapped_column(Float, default=0.85)
    visible: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    @property
    def tile_prefix(self) -> str:
        return f"allotments/{self.allotment_id}/layers/{self.id}/tiles"


class MapSuggestion(db.Model):
    """Something the detector found, waiting for a person to accept it as a map feature."""

    __tablename__ = "map_suggestions"

    id: Mapped[int] = mapped_column(primary_key=True)
    allotment_id: Mapped[int] = mapped_column(
        ForeignKey("allotments.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[int | None] = mapped_column(
        ForeignKey("map_jobs.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(20))  # FeatureKind value
    name: Mapped[str] = mapped_column(String(120))
    geometry: Mapped[dict] = mapped_column(JSON)  # GeoJSON: a Point (with radius_m) or a Polygon
    radius_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    views: Mapped[int] = mapped_column(default=1)  # how many photos saw it
    status: Mapped[str] = mapped_column(
        String(10), default="pending", index=True
    )  # pending | accepted | dismissed
    feature_id: Mapped[int | None] = mapped_column(
        ForeignKey("map_features.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
