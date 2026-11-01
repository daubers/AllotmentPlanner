"""admin flag and the log table behind the admin page

Revision ID: c29f5d1a7e36
Revises: b18e4c0fa597
"""

import sqlalchemy as sa
from alembic import op

revision = "c29f5d1a7e36"
down_revision = "b18e4c0fa597"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users", sa.Column("is_admin", sa.Boolean(), server_default="false", nullable=False)
    )
    op.create_table(
        "log_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("service", sa.String(20), nullable=False),
        sa.Column("host", sa.String(100), nullable=False),
        sa.Column("level", sa.String(10), nullable=False),
        sa.Column("event", sa.Text(), nullable=False),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("task_id", sa.String(64), nullable=True),
        sa.Column("data", sa.JSON(), nullable=True),
    )
    op.create_index("ix_log_entries_at", "log_entries", ["at"])
    op.create_index("ix_log_entries_level", "log_entries", ["level"])
    op.create_index("ix_log_entries_request_id", "log_entries", ["request_id"])
    op.create_index("ix_log_entries_task_id", "log_entries", ["task_id"])


def downgrade():
    op.drop_table("log_entries")
    op.drop_column("users", "is_admin")
