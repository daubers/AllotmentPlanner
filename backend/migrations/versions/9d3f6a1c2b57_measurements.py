"""measuring checklist

Revision ID: 9d3f6a1c2b57
Revises: 7c1d5e2a9b40
Create Date: 2026-10-28 23:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9d3f6a1c2b57'
down_revision = '7c1d5e2a9b40'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'allotments',
        sa.Column('length_unit', sa.String(length=8), server_default='m', nullable=False),
    )
    op.create_table(
        'measurements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('allotment_id', sa.Integer(), nullable=False),
        sa.Column('feature_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=10), nullable=False),
        sa.Column('a', sa.Integer(), nullable=False),
        sa.Column('b', sa.Integer(), nullable=False),
        sa.Column('value_m', sa.Float(), nullable=True),
        sa.Column('note', sa.String(length=300), nullable=False),
        sa.Column('skipped', sa.Boolean(), nullable=False),
        sa.Column('stale', sa.Boolean(), nullable=False),
        sa.Column('measured_by', sa.Integer(), nullable=True),
        sa.Column('measured_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['allotment_id'], ['allotments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['feature_id'], ['map_features.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['measured_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('feature_id', 'a', 'b', 'kind', name='uq_measurement_pair'),
    )
    op.create_index(op.f('ix_measurements_allotment_id'), 'measurements', ['allotment_id'])
    op.create_index(op.f('ix_measurements_feature_id'), 'measurements', ['feature_id'])


def downgrade():
    op.drop_index(op.f('ix_measurements_feature_id'), table_name='measurements')
    op.drop_index(op.f('ix_measurements_allotment_id'), table_name='measurements')
    op.drop_table('measurements')
    op.drop_column('allotments', 'length_unit')
