"""plan_items: what to grow in each bed and when (the crop plan)

Revision ID: j5a27b9f3d04
Revises: d71abfe46e8c
"""

import sqlalchemy as sa
from alembic import op

revision = "j5a27b9f3d04"
down_revision = "d71abfe46e8c"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "plan_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "allotment_id",
            sa.Integer(),
            sa.ForeignKey("allotments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "feature_id",
            sa.Integer(),
            sa.ForeignKey("map_features.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("crop_key", sa.String(40), nullable=True),
        sa.Column(
            "packet_id",
            sa.Integer(),
            sa.ForeignKey("seed_packets.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("method", sa.String(12), nullable=False, server_default="direct_sow"),
        sa.Column("area_m2", sa.Float(), nullable=False),
        sa.Column("plant_count", sa.Integer(), nullable=True),
        sa.Column("sow_on", sa.Date(), nullable=False),
        sa.Column("plant_out_on", sa.Date(), nullable=True),
        sa.Column("end_on", sa.Date(), nullable=False),
        sa.Column("series_key", sa.String(36), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(10), nullable=False, server_default="planned"),
        sa.Column(
            "planting_id",
            sa.Integer(),
            sa.ForeignKey("plantings.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("area_m2 > 0", name="ck_plan_items_area"),
        sa.CheckConstraint("plant_out_on IS NULL OR plant_out_on >= sow_on", name="ck_plan_items_plant_out"),
        sa.CheckConstraint("end_on >= COALESCE(plant_out_on, sow_on)", name="ck_plan_items_end"),
    )
    op.create_index("ix_plan_items_allotment_id", "plan_items", ["allotment_id"])
    op.create_index("ix_plan_items_feature_id", "plan_items", ["feature_id"])
    op.create_index("ix_plan_items_packet_id", "plan_items", ["packet_id"])
    op.create_index("ix_plan_items_series_key", "plan_items", ["series_key"])


def downgrade():
    op.drop_index("ix_plan_items_series_key", table_name="plan_items")
    op.drop_index("ix_plan_items_packet_id", table_name="plan_items")
    op.drop_index("ix_plan_items_feature_id", table_name="plan_items")
    op.drop_index("ix_plan_items_allotment_id", table_name="plan_items")
    op.drop_table("plan_items")
