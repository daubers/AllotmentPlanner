"""packet scans (reading a packet photo into a draft), and the seed count on a packet

Revision ID: c63d9f5e0a42
Revises: b52c8e4d9f31
Create Date: 2026-10-29 15:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c63d9f5e0a42'
down_revision = 'b52c8e4d9f31'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('seed_packets', sa.Column('seeds_in_packet', sa.Integer(), nullable=True))
    op.create_table(
        'packet_scans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('allotment_id', sa.Integer(), nullable=False),
        sa.Column('media_id', sa.Integer(), nullable=True),
        sa.Column('packet_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=10), nullable=False),
        sa.Column('error', sa.String(length=500), nullable=True),
        sa.Column('calendar_source', sa.String(length=10), nullable=True),
        sa.Column('rotation', sa.Integer(), nullable=False),
        sa.Column('missing', sa.JSON(), nullable=False),
        sa.Column('crop_media_id', sa.Integer(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['allotment_id'], ['allotments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['media_id'], ['media.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['packet_id'], ['seed_packets.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['crop_media_id'], ['media.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_packet_scans_allotment_id'), 'packet_scans', ['allotment_id'])
    op.create_index(op.f('ix_packet_scans_packet_id'), 'packet_scans', ['packet_id'])
    op.create_index(op.f('ix_packet_scans_status'), 'packet_scans', ['status'])


def downgrade():
    op.drop_index(op.f('ix_packet_scans_status'), table_name='packet_scans')
    op.drop_index(op.f('ix_packet_scans_packet_id'), table_name='packet_scans')
    op.drop_index(op.f('ix_packet_scans_allotment_id'), table_name='packet_scans')
    op.drop_table('packet_scans')
    op.drop_column('seed_packets', 'seeds_in_packet')
