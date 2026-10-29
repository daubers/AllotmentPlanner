"""map suggestions remember which photos showed them, and where

Revision ID: f96a2c8d3e75
Revises: e85f1b7c2d64
Create Date: 2026-10-29 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f96a2c8d3e75'
down_revision = 'e85f1b7c2d64'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('map_suggestions', sa.Column('sightings', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('map_suggestions', 'sightings')
