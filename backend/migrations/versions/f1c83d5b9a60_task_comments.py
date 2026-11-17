"""task comments: timestamped comments on tasks, each able to carry a status update

Revision ID: f1c83d5b9a60
Revises: e4b17c9a5d28
"""

import sqlalchemy as sa
from alembic import op

revision = "f1c83d5b9a60"
down_revision = "e4b17c9a5d28"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "task_comments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("allotment_id", sa.Integer(), sa.ForeignKey("allotments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(10), nullable=True),
        sa.Column("progress", sa.String(80), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_task_comments_allotment_id", "task_comments", ["allotment_id"])
    op.create_index("ix_task_comments_task_id", "task_comments", ["task_id"])
    op.create_index("ix_task_comments_created_at", "task_comments", ["created_at"])


def downgrade():
    op.drop_table("task_comments")
