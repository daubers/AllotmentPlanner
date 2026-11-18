"""account exports: a zip of a user's data, built in the background

Revision ID: i4f16a8e2d93
Revises: h3e05f7d1c82
"""

import sqlalchemy as sa
from alembic import op

revision = "i4f16a8e2d93"
down_revision = "h3e05f7d1c82"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "account_exports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("status", sa.String(10), nullable=False, server_default="pending"),
        sa.Column("storage_key", sa.String(255), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("error", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_account_exports_user_id", "account_exports", ["user_id"])
    op.create_index("ix_account_exports_expires_at", "account_exports", ["expires_at"])


def downgrade():
    op.drop_index("ix_account_exports_expires_at", table_name="account_exports")
    op.drop_index("ix_account_exports_user_id", table_name="account_exports")
    op.drop_table("account_exports")
