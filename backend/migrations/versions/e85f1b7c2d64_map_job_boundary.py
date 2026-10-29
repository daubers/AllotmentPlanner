"""map jobs can carry a plot boundary (from a GPX trace)

Revision ID: e85f1b7c2d64
Revises: d74e0a6f1b53
Create Date: 2026-10-29 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e85f1b7c2d64'
down_revision = 'd74e0a6f1b53'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('map_jobs', sa.Column('boundary', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('map_jobs', 'boundary')
