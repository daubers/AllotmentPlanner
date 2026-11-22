"""visits: planned trips to the allotment, with pegged tasks and an ics feed token

Revision ID: d71abfe46e8c
Revises: i4f16a8e2d93
"""

import sqlalchemy as sa
from alembic import op

revision = "d71abfe46e8c"
down_revision = "i4f16a8e2d93"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("allotments", sa.Column("calendar_token", sa.String(43), nullable=True))
    op.create_unique_constraint(
        "uq_allotments_calendar_token", "allotments", ["calendar_token"]
    )

    op.create_table(
        "visits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "allotment_id",
            sa.Integer(),
            sa.ForeignKey("allotments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="120"),
        sa.Column(
            "created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_visits_allotment_id", "visits", ["allotment_id"])
    op.create_index("ix_visits_starts_at", "visits", ["starts_at"])

    op.create_table(
        "visit_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "visit_id", sa.Integer(), sa.ForeignKey("visits.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("visit_id", "task_id", name="uq_visit_task"),
    )
    op.create_index("ix_visit_tasks_visit_id", "visit_tasks", ["visit_id"])
    op.create_index("ix_visit_tasks_task_id", "visit_tasks", ["task_id"])


def downgrade():
    op.drop_index("ix_visit_tasks_task_id", table_name="visit_tasks")
    op.drop_index("ix_visit_tasks_visit_id", table_name="visit_tasks")
    op.drop_table("visit_tasks")

    op.drop_index("ix_visits_starts_at", table_name="visits")
    op.drop_index("ix_visits_allotment_id", table_name="visits")
    op.drop_table("visits")

    op.drop_constraint("uq_allotments_calendar_token", "allotments", type_="unique")
    op.drop_column("allotments", "calendar_token")
