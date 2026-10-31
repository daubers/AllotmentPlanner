"""tasks can be pinned to a tray or planting and carry a suggestion key

Revision ID: b18e4c0fa597
Revises: a07b3d9e4f86
Create Date: 2026-10-31 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b18e4c0fa597'
down_revision = 'a07b3d9e4f86'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('tasks', sa.Column('tray_id', sa.Integer(), nullable=True))
    op.add_column('tasks', sa.Column('planting_id', sa.Integer(), nullable=True))
    op.add_column('tasks', sa.Column('suggestion_key', sa.String(length=100), nullable=True))
    op.create_index(op.f('ix_tasks_tray_id'), 'tasks', ['tray_id'], unique=False)
    op.create_index(op.f('ix_tasks_planting_id'), 'tasks', ['planting_id'], unique=False)
    op.create_foreign_key('fk_tasks_tray_id', 'tasks', 'trays', ['tray_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key(
        'fk_tasks_planting_id', 'tasks', 'plantings', ['planting_id'], ['id'], ondelete='SET NULL'
    )
    op.create_unique_constraint('uq_task_suggestion_key', 'tasks', ['allotment_id', 'suggestion_key'])


def downgrade():
    op.drop_constraint('uq_task_suggestion_key', 'tasks', type_='unique')
    op.drop_constraint('fk_tasks_planting_id', 'tasks', type_='foreignkey')
    op.drop_constraint('fk_tasks_tray_id', 'tasks', type_='foreignkey')
    op.drop_index(op.f('ix_tasks_planting_id'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_tray_id'), table_name='tasks')
    op.drop_column('tasks', 'suggestion_key')
    op.drop_column('tasks', 'planting_id')
    op.drop_column('tasks', 'tray_id')
