"""task_series: jobs that repeat on a schedule, created ahead as ordinary tasks

Revision ID: k6b38c0a4e15
Revises: j5a27b9f3d04
"""

import sqlalchemy as sa
from alembic import op

revision = "k6b38c0a4e15"
down_revision = "j5a27b9f3d04"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "task_series",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "allotment_id",
            sa.Integer(),
            sa.ForeignKey("allotments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("priority", sa.String(10), nullable=False, server_default="normal"),
        sa.Column(
            "assignee_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "feature_id",
            sa.Integer(),
            sa.ForeignKey("map_features.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("every_n", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("unit", sa.String(5), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("until_on", sa.Date(), nullable=False),
        sa.Column(
            "created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("every_n >= 1", name="ck_task_series_every"),
        sa.CheckConstraint("until_on >= starts_on", name="ck_task_series_dates"),
    )
    op.create_index("ix_task_series_allotment_id", "task_series", ["allotment_id"])

    op.add_column("tasks", sa.Column("series_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_tasks_series_id", "tasks", "task_series", ["series_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_tasks_series_id", "tasks", ["series_id"])


def downgrade():
    op.drop_index("ix_tasks_series_id", table_name="tasks")
    op.drop_constraint("fk_tasks_series_id", "tasks", type_="foreignkey")
    op.drop_column("tasks", "series_id")
    op.drop_index("ix_task_series_allotment_id", table_name="task_series")
    op.drop_table("task_series")
