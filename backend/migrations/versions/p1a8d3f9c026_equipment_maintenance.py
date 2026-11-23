"""equipment maintenance: a schedule and its jobs can be about a piece of equipment

Revision ID: p1a8d3f9c026
Revises: o0f7c2e8b159
"""

import sqlalchemy as sa
from alembic import op

revision = "p1a8d3f9c026"
down_revision = "o0f7c2e8b159"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("task_series", "tasks"):
        op.add_column(table, sa.Column("equipment_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_equipment_id", table, "equipment", ["equipment_id"], ["id"], ondelete="SET NULL"
        )
        op.create_index(f"ix_{table}_equipment_id", table, ["equipment_id"])


def downgrade():
    for table in ("tasks", "task_series"):
        op.drop_index(f"ix_{table}_equipment_id", table_name=table)
        op.drop_constraint(f"fk_{table}_equipment_id", table, type_="foreignkey")
        op.drop_column(table, "equipment_id")
