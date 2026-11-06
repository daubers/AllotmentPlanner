"""feature notes: dated notes on map features

Revision ID: e4b17c9a5d28
Revises: d3a06e2b8f47
"""

import sqlalchemy as sa
from alembic import op

revision = "e4b17c9a5d28"
down_revision = "d3a06e2b8f47"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "feature_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("allotment_id", sa.Integer(), sa.ForeignKey("allotments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("feature_id", sa.Integer(), sa.ForeignKey("map_features.id", ondelete="CASCADE"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("noted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_feature_notes_allotment_id", "feature_notes", ["allotment_id"])
    op.create_index("ix_feature_notes_feature_id", "feature_notes", ["feature_id"])
    op.create_index("ix_feature_notes_noted_at", "feature_notes", ["noted_at"])


def downgrade():
    op.drop_table("feature_notes")
