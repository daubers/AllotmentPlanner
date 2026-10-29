"""seed packets, and photos linked to them

Revision ID: a41f7b3c8d20
Revises: 9d3f6a1c2b57
Create Date: 2026-10-29 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a41f7b3c8d20'
down_revision = '9d3f6a1c2b57'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'seed_packets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('allotment_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=10), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('variety', sa.String(length=200), nullable=False),
        sa.Column('supplier', sa.String(length=200), nullable=False),
        sa.Column('latin_name', sa.String(length=200), nullable=False),
        sa.Column('notes', sa.Text(), nullable=False),
        sa.Column('raw_text', sa.Text(), nullable=False),
        sa.Column('sow_depth_mm', sa.Integer(), nullable=True),
        sa.Column('spacing_plant_cm', sa.Integer(), nullable=True),
        sa.Column('spacing_row_cm', sa.Integer(), nullable=True),
        sa.Column('germinate_days_min', sa.Integer(), nullable=True),
        sa.Column('germinate_days_max', sa.Integer(), nullable=True),
        sa.Column('maturity_days_min', sa.Integer(), nullable=True),
        sa.Column('maturity_days_max', sa.Integer(), nullable=True),
        sa.Column('sun', sa.String(length=10), nullable=True),
        sa.Column('stock', sa.String(length=10), nullable=False),
        sa.Column('best_before_year', sa.Integer(), nullable=True),
        sa.Column('calendar', sa.JSON(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['allotment_id'], ['allotments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_seed_packets_allotment_id'), 'seed_packets', ['allotment_id'])
    op.add_column('media', sa.Column('packet_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_media_packet_id'), 'media', ['packet_id'])
    op.create_foreign_key(
        'fk_media_packet_id', 'media', 'seed_packets', ['packet_id'], ['id'], ondelete='SET NULL'
    )


def downgrade():
    op.drop_constraint('fk_media_packet_id', 'media', type_='foreignkey')
    op.drop_index(op.f('ix_media_packet_id'), table_name='media')
    op.drop_column('media', 'packet_id')
    op.drop_index(op.f('ix_seed_packets_allotment_id'), table_name='seed_packets')
    op.drop_table('seed_packets')
