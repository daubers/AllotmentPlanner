"""tasks.plan_item_id: the crop plan item a task made from the plan is about

Revision ID: l7c49d1b5f26
Revises: k6b38c0a4e15
"""

import sqlalchemy as sa
from alembic import op

revision = "l7c49d1b5f26"
down_revision = "k6b38c0a4e15"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("tasks", sa.Column("plan_item_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_tasks_plan_item_id", "tasks", "plan_items", ["plan_item_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_tasks_plan_item_id", "tasks", ["plan_item_id"])


def downgrade():
    op.drop_index("ix_tasks_plan_item_id", table_name="tasks")
    op.drop_constraint("fk_tasks_plan_item_id", "tasks", type_="foreignkey")
    op.drop_column("tasks", "plan_item_id")
