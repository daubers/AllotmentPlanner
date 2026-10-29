"""seed trays and their cells; photos linked to a tray

Revision ID: b52c8e4d9f31
Revises: a41f7b3c8d20
Create Date: 2026-10-29 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b52c8e4d9f31'
down_revision = 'a41f7b3c8d20'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'trays',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('allotment_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('rows', sa.Integer(), nullable=False),
        sa.Column('cols', sa.Integer(), nullable=False),
        sa.Column('tray_type', sa.String(length=100), nullable=False),
        sa.Column('sown_on', sa.Date(), nullable=True),
        sa.Column('location', sa.String(length=200), nullable=False),
        sa.Column('notes', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=12), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['allotment_id'], ['allotments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_trays_allotment_id'), 'trays', ['allotment_id'])
    op.create_table(
        'tray_cells',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tray_id', sa.Integer(), nullable=False),
        sa.Column('row', sa.Integer(), nullable=False),
        sa.Column('col', sa.Integer(), nullable=False),
        sa.Column('packet_id', sa.Integer(), nullable=True),
        sa.Column('count', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=12), nullable=False),
        sa.Column('sown_on', sa.Date(), nullable=True),
        sa.Column('germinated_on', sa.Date(), nullable=True),
        sa.Column('note', sa.String(length=500), nullable=False),
        sa.ForeignKeyConstraint(['tray_id'], ['trays.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['packet_id'], ['seed_packets.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tray_id', 'row', 'col', name='uq_tray_cell'),
    )
    op.create_index(op.f('ix_tray_cells_tray_id'), 'tray_cells', ['tray_id'])
    op.create_index(op.f('ix_tray_cells_packet_id'), 'tray_cells', ['packet_id'])
    op.add_column('media', sa.Column('tray_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_media_tray_id'), 'media', ['tray_id'])
    op.create_foreign_key('fk_media_tray_id', 'media', 'trays', ['tray_id'], ['id'], ondelete='SET NULL')


def downgrade():
    op.drop_constraint('fk_media_tray_id', 'media', type_='foreignkey')
    op.drop_index(op.f('ix_media_tray_id'), table_name='media')
    op.drop_column('media', 'tray_id')
    op.drop_index(op.f('ix_tray_cells_packet_id'), table_name='tray_cells')
    op.drop_index(op.f('ix_tray_cells_tray_id'), table_name='tray_cells')
    op.drop_table('tray_cells')
    op.drop_index(op.f('ix_trays_allotment_id'), table_name='trays')
    op.drop_table('trays')
