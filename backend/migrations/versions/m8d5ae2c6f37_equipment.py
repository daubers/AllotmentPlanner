"""equipment: tools and equipment you own

Revision ID: m8d5ae2c6f37
Revises: l7c49d1b5f26
"""

import sqlalchemy as sa
from alembic import op

revision = "m8d5ae2c6f37"
down_revision = "l7c49d1b5f26"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "equipment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "allotment_id",
            sa.Integer(),
            sa.ForeignKey("allotments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(30), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("used_for", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="in_service"),
        sa.Column(
            "location_feature_id",
            sa.Integer(),
            sa.ForeignKey("map_features.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("last_serviced_on", sa.Date(), nullable=True),
        sa.Column(
            "created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity >= 1", name="ck_equipment_quantity"),
        sa.CheckConstraint("status IN ('in_service', 'out_of_action')", name="ck_equipment_status"),
    )
    op.create_index("ix_equipment_allotment_id", "equipment", ["allotment_id"])


def downgrade():
    op.drop_index("ix_equipment_allotment_id", table_name="equipment")
    op.drop_table("equipment")
