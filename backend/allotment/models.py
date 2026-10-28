import enum
from datetime import UTC, date, datetime

from geoalchemy2 import Geometry
from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
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
