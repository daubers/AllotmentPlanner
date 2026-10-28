"""media: where the position came from, capture session, client id

Revision ID: 7c1d5e2a9b40
Revises: 59bb86c05f2d
Create Date: 2026-10-28 22:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7c1d5e2a9b40'
down_revision = '59bb86c05f2d'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('media', sa.Column('position_source', sa.String(length=10), nullable=True))
    op.add_column('media', sa.Column('capture_session', sa.String(length=64), nullable=True))
    op.add_column('media', sa.Column('client_id', sa.String(length=64), nullable=True))
    op.create_index(op.f('ix_media_capture_session'), 'media', ['capture_session'])
    op.create_unique_constraint('uq_media_client_id', 'media', ['allotment_id', 'client_id'])
    # Positions that exist today came from the file itself, or were set by hand.
    op.execute("UPDATE media SET position_source = 'exif' WHERE lat IS NOT NULL")


def downgrade():
    op.drop_constraint('uq_media_client_id', 'media', type_='unique')
    op.drop_index(op.f('ix_media_capture_session'), table_name='media')
    op.drop_column('media', 'client_id')
    op.drop_column('media', 'capture_session')
    op.drop_column('media', 'position_source')
