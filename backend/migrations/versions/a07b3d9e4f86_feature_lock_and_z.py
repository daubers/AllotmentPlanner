"""map features can be locked and stacked

Revision ID: a07b3d9e4f86
Revises: f96a2c8d3e75
Create Date: 2026-10-30 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a07b3d9e4f86'
down_revision = 'f96a2c8d3e75'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('map_features', sa.Column('locked', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('map_features', sa.Column('z', sa.Integer(), server_default='0', nullable=False))


def downgrade():
    op.drop_column('map_features', 'z')
    op.drop_column('map_features', 'locked')
