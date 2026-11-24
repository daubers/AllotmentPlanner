"""equipment_bookings: equipment put to use on a bed or a planting for a stretch of time

Revision ID: q2b9e4a1d137
Revises: p1a8d3f9c026
"""

import sqlalchemy as sa
from alembic import op

revision = "q2b9e4a1d137"
down_revision = "p1a8d3f9c026"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "equipment_bookings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "allotment_id",
            sa.Integer(),
            sa.ForeignKey("allotments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "equipment_id",
            sa.Integer(),
            sa.ForeignKey("equipment.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "feature_id",
            sa.Integer(),
            sa.ForeignKey("map_features.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "planting_id",
            sa.Integer(),
            sa.ForeignKey("plantings.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity >= 1", name="ck_equipment_bookings_quantity"),
        sa.CheckConstraint("ends_on > starts_on", name="ck_equipment_bookings_dates"),
        sa.CheckConstraint(
            "(feature_id IS NULL) <> (planting_id IS NULL)", name="ck_equipment_bookings_target"
        ),
    )
    for col in ("allotment_id", "equipment_id", "feature_id", "planting_id"):
        op.create_index(f"ix_equipment_bookings_{col}", "equipment_bookings", [col])


def downgrade():
    for col in ("planting_id", "feature_id", "equipment_id", "allotment_id"):
        op.drop_index(f"ix_equipment_bookings_{col}", table_name="equipment_bookings")
    op.drop_table("equipment_bookings")
