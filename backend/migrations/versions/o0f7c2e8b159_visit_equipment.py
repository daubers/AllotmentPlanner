"""visit_equipment: hand-made changes to a visit's bring list

Revision ID: o0f7c2e8b159
Revises: n9e6b1d7a048
"""

import sqlalchemy as sa
from alembic import op

revision = "o0f7c2e8b159"
down_revision = "n9e6b1d7a048"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "visit_equipment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "allotment_id",
            sa.Integer(),
            sa.ForeignKey("allotments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "visit_id", sa.Integer(), sa.ForeignKey("visits.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "equipment_id",
            sa.Integer(),
            sa.ForeignKey("equipment.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("mode", sa.String(10), nullable=False),
        sa.Column(
            "created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("visit_id", "equipment_id", name="uq_visit_equipment"),
        sa.CheckConstraint("mode IN ('add', 'remove')", name="ck_visit_equipment_mode"),
    )
    op.create_index("ix_visit_equipment_allotment_id", "visit_equipment", ["allotment_id"])
    op.create_index("ix_visit_equipment_visit_id", "visit_equipment", ["visit_id"])
    op.create_index("ix_visit_equipment_equipment_id", "visit_equipment", ["equipment_id"])


def downgrade():
    op.drop_index("ix_visit_equipment_equipment_id", table_name="visit_equipment")
    op.drop_index("ix_visit_equipment_visit_id", table_name="visit_equipment")
    op.drop_index("ix_visit_equipment_allotment_id", table_name="visit_equipment")
    op.drop_table("visit_equipment")
