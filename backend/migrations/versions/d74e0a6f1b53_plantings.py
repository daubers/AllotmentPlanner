"""plantings (regions in beds), cells that went into them, photos of them

Revision ID: d74e0a6f1b53
Revises: c63d9f5e0a42
Create Date: 2026-10-29 17:00:00.000000

"""
from alembic import op
import geoalchemy2  # noqa: F401
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd74e0a6f1b53'
down_revision = 'c63d9f5e0a42'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'plantings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('allotment_id', sa.Integer(), nullable=False),
        sa.Column('feature_id', sa.Integer(), nullable=False),
        sa.Column('packet_id', sa.Integer(), nullable=True),
        sa.Column('tray_id', sa.Integer(), nullable=True),
        sa.Column('region', geoalchemy2.types.Geometry(geometry_type='POLYGON', srid=4326, dimension=2, from_text='ST_GeomFromEWKT', name='geometry', nullable=False), nullable=False),
        sa.Column('count', sa.Integer(), nullable=True),
        sa.Column('method', sa.String(length=12), nullable=False),
        sa.Column('status', sa.String(length=10), nullable=False),
        sa.Column('sown_on', sa.Date(), nullable=True),
        sa.Column('planted_on', sa.Date(), nullable=True),
        sa.Column('harvested_on', sa.Date(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['allotment_id'], ['allotments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['feature_id'], ['map_features.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['packet_id'], ['seed_packets.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tray_id'], ['trays.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_plantings_allotment_id'), 'plantings', ['allotment_id'])
    op.create_index(op.f('ix_plantings_feature_id'), 'plantings', ['feature_id'])
    op.create_index(op.f('ix_plantings_packet_id'), 'plantings', ['packet_id'])
    op.create_index(op.f('ix_plantings_tray_id'), 'plantings', ['tray_id'])
    op.create_index(op.f('ix_plantings_status'), 'plantings', ['status'])
    op.add_column('tray_cells', sa.Column('planting_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_tray_cells_planting_id'), 'tray_cells', ['planting_id'])
    op.create_foreign_key('fk_tray_cells_planting_id', 'tray_cells', 'plantings', ['planting_id'], ['id'], ondelete='SET NULL')
    op.add_column('media', sa.Column('planting_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_media_planting_id'), 'media', ['planting_id'])
    op.create_foreign_key('fk_media_planting_id', 'media', 'plantings', ['planting_id'], ['id'], ondelete='SET NULL')


def downgrade():
    op.drop_constraint('fk_media_planting_id', 'media', type_='foreignkey')
    op.drop_index(op.f('ix_media_planting_id'), table_name='media')
    op.drop_column('media', 'planting_id')
    op.drop_constraint('fk_tray_cells_planting_id', 'tray_cells', type_='foreignkey')
    op.drop_index(op.f('ix_tray_cells_planting_id'), table_name='tray_cells')
    op.drop_column('tray_cells', 'planting_id')
    for ix in ('status', 'tray_id', 'packet_id', 'feature_id', 'allotment_id'):
        op.drop_index(op.f(f'ix_plantings_{ix}'), table_name='plantings')
    op.drop_table('plantings')
