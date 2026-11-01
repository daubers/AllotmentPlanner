"""day lists: hand-picked lists of tasks

Revision ID: d3a06e2b8f47
Revises: c29f5d1a7e36
"""

import sqlalchemy as sa
from alembic import op

revision = "d3a06e2b8f47"
down_revision = "c29f5d1a7e36"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "day_lists",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("allotment_id", sa.Integer(), sa.ForeignKey("allotments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("date", sa.Date(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_day_lists_allotment_id", "day_lists", ["allotment_id"])
    op.create_table(
        "day_list_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("list_id", sa.Integer(), sa.ForeignKey("day_lists.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("list_id", "task_id", name="uq_day_list_task"),
    )
    op.create_index("ix_day_list_items_list_id", "day_list_items", ["list_id"])
    op.create_index("ix_day_list_items_task_id", "day_list_items", ["task_id"])


def downgrade():
    op.drop_table("day_list_items")
    op.drop_table("day_lists")
