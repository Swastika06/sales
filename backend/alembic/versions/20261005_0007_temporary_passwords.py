"""Emailed onboarding credentials and required first-login password change."""

import sqlalchemy as sa

from alembic import op

revision = "20261005_0007"
down_revision = "20261001_0006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("onboarding_applications", sa.Column("access_password_hash", sa.String(255)))
    op.add_column(
        "onboarding_applications", sa.Column("access_expires_at", sa.DateTime(timezone=True))
    )


def downgrade():
    op.drop_column("onboarding_applications", "access_expires_at")
    op.drop_column("onboarding_applications", "access_password_hash")
    op.drop_column("users", "must_change_password")
