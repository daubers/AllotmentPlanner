import enum
from datetime import UTC, date, datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
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
    # Null for someone who has only signed in through an OIDC provider.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Can open the admin page (worker state, jobs, logs). Set with `flask make-admin`.
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class OidcIdentity(db.Model):
    """A login at an OIDC provider, tied to a user. `subject` is the provider's id for them."""

    __tablename__ = "oidc_identities"
    __table_args__ = (UniqueConstraint("provider", "subject", name="uq_oidc_provider_subject"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(64))
    subject: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class OidcLoginCode(db.Model):
    """A one-time code the browser or phone swaps for tokens, so tokens never travel in a URL.

    Only a hash is stored. It is deleted when used and is worthless after `expires_at`.
    """

    __tablename__ = "oidc_login_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # "login" is swapped for tokens; "link" starts linking a provider to the signed-in user.
    # A code only works for its own purpose, so a link code can never sign anyone in.
    purpose: Mapped[str] = mapped_column(String(8), default="login", server_default="login")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class Allotment(db.Model):
    __tablename__ = "allotments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    length_unit: Mapped[str] = mapped_column(
        String(8), default="m", server_default="m"
    )  # how lengths are shown: m | cm | ft_in (always stored in metres)
    # The secret in the public .ics feed URL. Null until first requested; rotating it
    # invalidates every calendar subscribed to the old one.
    calendar_token: Mapped[str | None] = mapped_column(String(43), nullable=True, unique=True)
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
    # A locked feature can't be moved, reshaped or deleted until it is unlocked.
    locked: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Stacking order on the map: higher is drawn on top; ties fall back to the kind's usual order.
    z: Mapped[int] = mapped_column(default=0, server_default="0")
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class Measurement(db.Model):
    """One distance to measure on site, between two corners of a drawn feature (or its radius)."""

    __tablename__ = "measurements"
    __table_args__ = (UniqueConstraint("feature_id", "a", "b", "kind", name="uq_measurement_pair"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    allotment_id: Mapped[int] = mapped_column(
        ForeignKey("allotments.id", ondelete="CASCADE"), index=True
    )
    feature_id: Mapped[int] = mapped_column(
        ForeignKey("map_features.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(10))  # edge | diagonal | radius | custom
    a: Mapped[int] = mapped_column()  # corner index, 0-based (the UI shows it plus one)
    b: Mapped[int] = mapped_column()
    value_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    note: Mapped[str] = mapped_column(String(300), default="")
    skipped: Mapped[bool] = mapped_column(Boolean, default=False)
    stale: Mapped[bool] = mapped_column(Boolean, default=False)  # its corners no longer exist
    measured_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    measured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class TaskComment(db.Model):
    """A timestamped comment on a task. It can also report progress: `status` is the task status
    this comment set (null if it left it alone) and `progress` is a short free-text label."""

    __tablename__ = "task_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    allotment_id: Mapped[int] = mapped_column(
        ForeignKey("allotments.id", ondelete="CASCADE"), index=True
    )
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str | None] = mapped_column(String(10), nullable=True)
    progress: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class FeatureNote(db.Model):
    """A dated note on a feature. Any number a day; `noted_at` is when it is about, and editable."""

    __tablename__ = "feature_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    allotment_id: Mapped[int] = mapped_column(
        ForeignKey("allotments.id", ondelete="CASCADE"), index=True
    )
    feature_id: Mapped[int] = mapped_column(
        ForeignKey("map_features.id", ondelete="CASCADE"), index=True
    )
    body: Mapped[str] = mapped_column(Text)
    noted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
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


class TaskSeries(db.Model):
    """A recurring job on a schedule: every N days, weeks or months until a date.

    Its occurrences are ordinary tasks created ahead of time (see allotment.task_series).
    """

    __tablename__ = "task_series"
    __table_args__ = (
        CheckConstraint("every_n >= 1", name="ck_task_series_every"),
        CheckConstraint("until_on >= starts_on", name="ck_task_series_dates"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    allotment_id: Mapped[int] = mapped_column(
        ForeignKey("allotments.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[str] = mapped_column(String(10), default="normal")
    assignee_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    feature_id: Mapped[int | None] = mapped_column(
        ForeignKey("map_features.id", ondelete="SET NULL"), nullable=True
    )
    every_n: Mapped[int] = mapped_column(default=1)
    unit: Mapped[str] = mapped_column(String(5))  # day | week | month
    starts_on: Mapped[date] = mapped_column(Date)
    until_on: Mapped[date] = mapped_column(Date)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Task(db.Model):
    """A job to do. Optionally pinned to a map feature and/or a point on the map."""

    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("allotment_id", "suggestion_key", name="uq_task_suggestion_key"),
    )

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
    tray_id: Mapped[int | None] = mapped_column(
        ForeignKey("trays.id", ondelete="SET NULL"), nullable=True, index=True
    )
    planting_id: Mapped[int | None] = mapped_column(
        ForeignKey("plantings.id", ondelete="SET NULL"), nullable=True, index=True
    )
    series_id: Mapped[int | None] = mapped_column(
        ForeignKey("task_series.id", ondelete="SET NULL"), nullable=True, index=True
    )  # the schedule this occurrence came from
    plan_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("plan_items.id", ondelete="SET NULL"), nullable=True, index=True
    )  # the crop plan item this job is about
    # Set on tasks made from a suggestion ("tray:12:germination"), so adding them twice is a no-op.
    suggestion_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
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
    packet_id: Mapped[int | None] = mapped_column(
        ForeignKey("seed_packets.id", ondelete="SET NULL"), nullable=True, index=True
    )
    tray_id: Mapped[int | None] = mapped_column(
        ForeignKey("trays.id", ondelete="SET NULL"), nullable=True, index=True
    )
    planting_id: Mapped[int | None] = mapped_column(
        ForeignKey("plantings.id", ondelete="SET NULL"), nullable=True, index=True
    )
    caption: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(10), default="pending")  # pending | ready | failed
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class SeedPacket(db.Model):
    """One seed packet in the library: what it is, how to grow it and when."""

    __tablename__ = "seed_packets"

    id: Mapped[int] = mapped_column(primary_key=True)
    allotment_id: Mapped[int] = mapped_column(
        ForeignKey("allotments.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(10), default="active")  # draft | active
    name: Mapped[str] = mapped_column(String(200))
    variety: Mapped[str] = mapped_column(String(200), default="")
    supplier: Mapped[str] = mapped_column(String(200), default="")
    latin_name: Mapped[str] = mapped_column(String(200), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    raw_text: Mapped[str] = mapped_column(Text, default="")  # as read from the packet
    sow_depth_mm: Mapped[int | None] = mapped_column(nullable=True)
    spacing_plant_cm: Mapped[int | None] = mapped_column(nullable=True)
    spacing_row_cm: Mapped[int | None] = mapped_column(nullable=True)
    germinate_days_min: Mapped[int | None] = mapped_column(nullable=True)
    germinate_days_max: Mapped[int | None] = mapped_column(nullable=True)
    maturity_days_min: Mapped[int | None] = mapped_column(nullable=True)
    maturity_days_max: Mapped[int | None] = mapped_column(nullable=True)
    sun: Mapped[str | None] = mapped_column(String(10), nullable=True)  # full | partial | shade
    stock: Mapped[str] = mapped_column(String(10), default="full")  # full | part | low | empty
    best_before_year: Mapped[int | None] = mapped_column(nullable=True)
    seeds_in_packet: Mapped[int | None] = mapped_column(nullable=True)
    # {"sow_indoors": [1, 2], "sow_outdoors": [...], "plant_out": [...], "harvest": [...]}
    calendar: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class PacketScan(db.Model):
    """A photo of a packet's back being read into a draft SeedPacket (OCR, ``vision`` queue)."""

    __tablename__ = "packet_scans"

    id: Mapped[int] = mapped_column(primary_key=True)
    allotment_id: Mapped[int] = mapped_column(
        ForeignKey("allotments.id", ondelete="CASCADE"), index=True
    )
    media_id: Mapped[int | None] = mapped_column(
        ForeignKey("media.id", ondelete="SET NULL"), nullable=True
    )
    packet_id: Mapped[int | None] = mapped_column(
        ForeignKey("seed_packets.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(10), default="queued", index=True)
    # queued | running | ready | failed
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    calendar_source: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )  # graphic | words
    rotation: Mapped[int] = mapped_column(default=0)
    missing: Mapped[list] = mapped_column(JSON, default=list)  # fields the reader could not find
    crop_media_id: Mapped[int | None] = mapped_column(
        ForeignKey("media.id", ondelete="SET NULL"), nullable=True
    )  # the calendar as read, for the review screen
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Tray(db.Model):
    """A seed tray: a grid of cells, each sown with a packet (several kinds per tray)."""

    __tablename__ = "trays"

    id: Mapped[int] = mapped_column(primary_key=True)
    allotment_id: Mapped[int] = mapped_column(
        ForeignKey("allotments.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    rows: Mapped[int] = mapped_column()
    cols: Mapped[int] = mapped_column()
    tray_type: Mapped[str] = mapped_column(String(100), default="")  # e.g. "24-cell module tray"
    sown_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    location: Mapped[str] = mapped_column(String(200), default="")  # e.g. "greenhouse, left shelf"
    notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(
        String(12), default="active"
    )  # active | planted_out | finished
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    cells: Mapped[list["TrayCell"]] = relationship(
        back_populates="tray", cascade="all, delete-orphan", order_by="TrayCell.row, TrayCell.col"
    )


class TrayCell(db.Model):
    """One occupied cell of a tray. A cell with no row is empty."""

    __tablename__ = "tray_cells"
    __table_args__ = (UniqueConstraint("tray_id", "row", "col", name="uq_tray_cell"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tray_id: Mapped[int] = mapped_column(ForeignKey("trays.id", ondelete="CASCADE"), index=True)
    row: Mapped[int] = mapped_column()  # 0-based
    col: Mapped[int] = mapped_column()
    packet_id: Mapped[int | None] = mapped_column(
        ForeignKey("seed_packets.id", ondelete="SET NULL"), nullable=True, index=True
    )
    count: Mapped[int | None] = mapped_column(nullable=True)  # seeds sown in the cell
    status: Mapped[str] = mapped_column(String(12), default="sown")
    sown_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    germinated_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str] = mapped_column(String(500), default="")
    planting_id: Mapped[int | None] = mapped_column(
        ForeignKey("plantings.id", ondelete="SET NULL"), nullable=True, index=True
    )  # where it went when planted out

    tray: Mapped[Tray] = relationship(back_populates="cells")


class Planting(db.Model):
    """Something growing in part of a bed: a drawn region, a packet, how and when it went in."""

    __tablename__ = "plantings"

    id: Mapped[int] = mapped_column(primary_key=True)
    allotment_id: Mapped[int] = mapped_column(
        ForeignKey("allotments.id", ondelete="CASCADE"), index=True
    )
    feature_id: Mapped[int] = mapped_column(
        ForeignKey("map_features.id", ondelete="CASCADE"), index=True
    )  # the bed
    packet_id: Mapped[int | None] = mapped_column(
        ForeignKey("seed_packets.id", ondelete="SET NULL"), nullable=True, index=True
    )
    tray_id: Mapped[int | None] = mapped_column(
        ForeignKey("trays.id", ondelete="SET NULL"), nullable=True, index=True
    )  # the tray it was planted out from
    region = mapped_column(Geometry("POLYGON", srid=4326), nullable=False)
    count: Mapped[int | None] = mapped_column(nullable=True)
    method: Mapped[str] = mapped_column(String(12), default="direct_sow")  # direct_sow | transplant
    status: Mapped[str] = mapped_column(String(10), default="sown", index=True)
    # sown | growing | harvesting | finished | failed
    sown_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    planted_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    harvested_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class PlanItem(db.Model):
    """Something you mean to grow in part of a bed, and when: one step of a crop plan.

    A succession is several items sharing a ``series_key``. The space is an amount (``area_m2``),
    not a drawn region: the bed is occupied from ``plant_out_on`` (or ``sow_on`` for a direct sow)
    up to, but not including, ``end_on``. Tray time before a transplant does not use the bed.
    """

    __tablename__ = "plan_items"
    __table_args__ = (
        CheckConstraint("area_m2 > 0", name="ck_plan_items_area"),
        CheckConstraint(
            "plant_out_on IS NULL OR plant_out_on >= sow_on", name="ck_plan_items_plant_out"
        ),
        CheckConstraint("end_on >= COALESCE(plant_out_on, sow_on)", name="ck_plan_items_end"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    allotment_id: Mapped[int] = mapped_column(
        ForeignKey("allotments.id", ondelete="CASCADE"), index=True
    )
    feature_id: Mapped[int] = mapped_column(
        ForeignKey("map_features.id", ondelete="CASCADE"), index=True
    )  # the bed
    crop_key: Mapped[str | None] = mapped_column(String(40), nullable=True)  # allotment.crops
    packet_id: Mapped[int | None] = mapped_column(
        ForeignKey("seed_packets.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(120))  # what to call it on the plan
    method: Mapped[str] = mapped_column(String(12), default="direct_sow")
    area_m2: Mapped[float] = mapped_column(Float)
    plant_count: Mapped[int | None] = mapped_column(nullable=True)
    sow_on: Mapped[date] = mapped_column(Date)
    plant_out_on: Mapped[date | None] = mapped_column(Date, nullable=True)  # transplants only
    end_on: Mapped[date] = mapped_column(Date)  # the day the bed is free again
    series_key: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(10), default="planned")  # planned | done | skipped
    planting_id: Mapped[int | None] = mapped_column(
        ForeignKey("plantings.id", ondelete="SET NULL"), nullable=True
    )  # the real planting this became
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class Equipment(db.Model):
    """Something you own to do the work: a spade, a set of cloches, a wheelbarrow."""

    __tablename__ = "equipment"
    __table_args__ = (
        CheckConstraint("quantity >= 1", name="ck_equipment_quantity"),
        CheckConstraint("status IN ('in_service', 'out_of_action')", name="ck_equipment_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    allotment_id: Mapped[int] = mapped_column(
        ForeignKey("allotments.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str | None] = mapped_column(String(30), nullable=True)  # allotment.equipment_kinds
    quantity: Mapped[int] = mapped_column(default=1, server_default="1")
    notes: Mapped[str] = mapped_column(Text, default="")
    # Words or phrases ("dig, double digging") that make this item suggested for a task.
    used_for: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(
        String(20), default="in_service", server_default="in_service"
    )  # in_service | out_of_action
    location_feature_id: Mapped[int | None] = mapped_column(
        ForeignKey("map_features.id", ondelete="SET NULL"), nullable=True
    )  # where it lives, usually a shed
    last_serviced_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


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
    # The plot boundary as a GeoJSON Polygon (from a GPX trace): helps place what the photos found.
    boundary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
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
    # Where it was seen, best first: [{media_id, outline: [[x, y]...] (0..1 of the photo), score}]
    sightings: Mapped[list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        String(10), default="pending", index=True
    )  # pending | accepted | dismissed
    feature_id: Mapped[int | None] = mapped_column(
        ForeignKey("map_features.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class LogEntry(db.Model):
    """A log line kept for the admin page: warnings and errors, plus task and job outcomes."""

    __tablename__ = "log_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    service: Mapped[str] = mapped_column(String(20))  # api | worker | beat
    host: Mapped[str] = mapped_column(String(100), default="")
    level: Mapped[str] = mapped_column(String(10), index=True)  # info | warning | error | critical
    event: Mapped[str] = mapped_column(Text)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class DayList(db.Model):
    """A hand-picked list of tasks for a day or a round of jobs; it prints as a todo sheet."""

    __tablename__ = "day_lists"

    id: Mapped[int] = mapped_column(primary_key=True)
    allotment_id: Mapped[int] = mapped_column(
        ForeignKey("allotments.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    # The day it is for, if any (not called `date`: that would hide the type in this class).
    for_date: Mapped[date | None] = mapped_column("date", Date, nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    items: Mapped[list["DayListItem"]] = relationship(
        back_populates="day_list", cascade="all, delete-orphan", order_by="DayListItem.id"
    )


class DayListItem(db.Model):
    __tablename__ = "day_list_items"
    __table_args__ = (UniqueConstraint("list_id", "task_id", name="uq_day_list_task"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    list_id: Mapped[int] = mapped_column(ForeignKey("day_lists.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    day_list: Mapped[DayList] = relationship(back_populates="items")


class Visit(db.Model):
    """A planned trip to the allotment, with a start time/duration and a pegged task list."""

    __tablename__ = "visits"

    id: Mapped[int] = mapped_column(primary_key=True)
    allotment_id: Mapped[int] = mapped_column(
        ForeignKey("allotments.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    notes: Mapped[str] = mapped_column(Text, default="")
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    duration_minutes: Mapped[int] = mapped_column(default=120, server_default="120")
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    tasks: Mapped[list["VisitTask"]] = relationship(
        back_populates="visit", cascade="all, delete-orphan", order_by="VisitTask.position"
    )


class VisitTask(db.Model):
    __tablename__ = "visit_tasks"
    __table_args__ = (UniqueConstraint("visit_id", "task_id", name="uq_visit_task"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visits.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(default=0, server_default="0")

    visit: Mapped[Visit] = relationship(back_populates="tasks")


class AccountExport(db.Model):
    """A zip of everything a user added, built in the background and kept for a short while."""

    __tablename__ = "account_exports"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(10), default="pending", server_default="pending")
    storage_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
