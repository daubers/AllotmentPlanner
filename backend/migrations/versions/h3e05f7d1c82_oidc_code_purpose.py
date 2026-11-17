"""oidc: a purpose on one-time codes, so a link code can never sign anyone in

Revision ID: h3e05f7d1c82
Revises: g2d94e6c0b71
"""

import sqlalchemy as sa
from alembic import op

revision = "h3e05f7d1c82"
down_revision = "g2d94e6c0b71"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "oidc_login_codes",
        sa.Column("purpose", sa.String(8), nullable=False, server_default="login"),
    )


def downgrade():
    op.drop_column("oidc_login_codes", "purpose")
