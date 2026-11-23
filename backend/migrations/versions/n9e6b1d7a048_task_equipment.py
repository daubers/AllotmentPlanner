"""task_equipment: the equipment a task needs

Revision ID: n9e6b1d7a048
Revises: m8d5ae2c6f37
"""

import sqlalchemy as sa
from alembic import op

revision = "n9e6b1d7a048"
down_revision = "m8d5ae2c6f37"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "task_equipment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "allotment_id",
            sa.Integer(),
            sa.ForeignKey("allotments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "equipment_id",
            sa.Integer(),
            sa.ForeignKey("equipment.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("task_id", "equipment_id", name="uq_task_equipment"),
    )
    op.create_index("ix_task_equipment_allotment_id", "task_equipment", ["allotment_id"])
    op.create_index("ix_task_equipment_task_id", "task_equipment", ["task_id"])
    op.create_index("ix_task_equipment_equipment_id", "task_equipment", ["equipment_id"])


def downgrade():
    op.drop_index("ix_task_equipment_equipment_id", table_name="task_equipment")
    op.drop_index("ix_task_equipment_task_id", table_name="task_equipment")
    op.drop_index("ix_task_equipment_allotment_id", table_name="task_equipment")
    op.drop_table("task_equipment")
