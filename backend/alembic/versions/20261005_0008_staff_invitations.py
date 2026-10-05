"""Staff invitations through the encrypted mail outbox and Finance role."""

import sqlalchemy as sa

from alembic import op

revision = "20261005_0008"
down_revision = "20261005_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("onboarding_mail", "application_id", nullable=True)
    op.add_column(
        "onboarding_mail",
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE")),
    )
    op.create_index("ix_onboarding_mail_user_id", "onboarding_mail", ["user_id"])
    op.execute(
        "INSERT INTO roles (id, code, name, created_at, updated_at) "
        "VALUES (gen_random_uuid(), 'TCG_FINANCE', 'TCG Finance', now(), now()) "
        "ON CONFLICT (code) DO NOTHING"
    )
    op.execute(
        "INSERT INTO role_permissions (role_id, permission_id) "
        "SELECT r.id, p.id FROM roles r CROSS JOIN permissions p "
        "WHERE r.code='TCG_FINANCE' AND p.code IN "
        "('partners.view','catalog.view','pricing.view','sales.view','documents.view') "
        "ON CONFLICT DO NOTHING"
    )


def downgrade() -> None:
    # Prevent a partial rollback that would orphan staff invitation history.
    staff_mail = op.get_bind().scalar(
        sa.text("SELECT count(*) FROM onboarding_mail WHERE application_id IS NULL")
    )
    if staff_mail:
        raise RuntimeError(
            "Archive and remove staff invitation mail before downgrading this migration"
        )
    op.alter_column("onboarding_mail", "application_id", nullable=False)
    op.drop_index("ix_onboarding_mail_user_id", table_name="onboarding_mail")
    op.drop_column("onboarding_mail", "user_id")
