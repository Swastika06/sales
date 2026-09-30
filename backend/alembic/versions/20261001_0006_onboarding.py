"""Private document review, legal assignment, OTP activation, and durable mail."""

from alembic import op

revision = "20261001_0006"
down_revision = "20260930_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
CREATE TABLE onboarding_applications (
	partner_id UUID NOT NULL, 
	applicant_id UUID NOT NULL, 
	status VARCHAR(40) NOT NULL, 
	revision INTEGER NOT NULL, 
	reviewed_revision INTEGER, 
	token_version INTEGER NOT NULL, 
	assigned_to_id UUID, 
	reviewed_by_id UUID, 
	review_comment TEXT, 
	submitted_at TIMESTAMP WITH TIME ZONE, 
	reviewed_at TIMESTAMP WITH TIME ZONE, 
	verified_at TIMESTAMP WITH TIME ZONE, 
	otp_hash VARCHAR(64), 
	otp_expires_at TIMESTAMP WITH TIME ZONE, 
	otp_sent_at TIMESTAMP WITH TIME ZONE, 
	otp_attempts INTEGER NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_onboarding_applications PRIMARY KEY (id), 
        CONSTRAINT ck_onboarding_applications_valid_status CHECK (status IN
('DRAFT','PENDING_ADMIN_REVIEW','LEGAL_REVIEW','CHANGES_REQUESTED','REJECTED','PENDING_EMAIL_VERIFICATION','COMPLETED')),
	CONSTRAINT uq_onboarding_applications_partner_id UNIQUE (partner_id), 
        CONSTRAINT fk_onboarding_applications_partner_id_partners FOREIGN KEY(partner_id)
REFERENCES partners (id),
        CONSTRAINT fk_onboarding_applications_applicant_id_users FOREIGN KEY(applicant_id)
REFERENCES users (id),
        CONSTRAINT fk_onboarding_applications_assigned_to_id_users FOREIGN KEY(assigned_to_id)
REFERENCES users (id),
        CONSTRAINT fk_onboarding_applications_reviewed_by_id_users FOREIGN KEY(reviewed_by_id)
REFERENCES users (id)
)
""")
    op.execute("""
CREATE INDEX ix_onboarding_applications_status ON onboarding_applications (status)
""")
    op.execute("""
CREATE TABLE onboarding_documents (
	application_id UUID NOT NULL, 
	kind VARCHAR(30) NOT NULL, 
	number VARCHAR(100) NOT NULL, 
	revision INTEGER NOT NULL, 
	filename VARCHAR(200) NOT NULL, 
	object_key VARCHAR(500) NOT NULL, 
	content_type VARCHAR(100) NOT NULL, 
	size INTEGER NOT NULL, 
	sha256 VARCHAR(64) NOT NULL, 
	scan_status VARCHAR(30) NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_onboarding_documents PRIMARY KEY (id), 
        CONSTRAINT fk_onboarding_documents_application_id_onboarding_applications FOREIGN
KEY(application_id) REFERENCES onboarding_applications (id) ON DELETE CASCADE,
	CONSTRAINT uq_onboarding_documents_object_key UNIQUE (object_key)
)
""")
    op.execute("""
CREATE INDEX ix_onboarding_documents_application_id ON onboarding_documents (application_id)
""")
    op.execute("""
CREATE TABLE onboarding_mail (
	application_id UUID NOT NULL, 
	kind VARCHAR(30) NOT NULL, 
	encrypted_payload TEXT, 
	status VARCHAR(20) NOT NULL, 
	attempts INTEGER NOT NULL, 
	available_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	sent_at TIMESTAMP WITH TIME ZONE, 
	last_error VARCHAR(100), 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_onboarding_mail PRIMARY KEY (id), 
        CONSTRAINT fk_onboarding_mail_application_id_onboarding_applications FOREIGN
KEY(application_id) REFERENCES onboarding_applications (id) ON DELETE CASCADE
)
""")
    op.execute("""
CREATE INDEX ix_onboarding_mail_application_id ON onboarding_mail (application_id)
""")
    op.execute("""
CREATE INDEX ix_onboarding_mail_status ON onboarding_mail (status)
""")
    op.execute("""
CREATE TABLE onboarding_rate_limits (
	key VARCHAR(64) NOT NULL, 
	count INTEGER NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	CONSTRAINT pk_onboarding_rate_limits PRIMARY KEY (key)
)
""")
    op.execute("""
INSERT INTO roles (id,code,name) VALUES ('10b9c4b0-b078-4628-b8fc-14077255c3ed','TCG_LEGAL','TCG
Legal') ON CONFLICT (code) DO NOTHING
""")
    op.execute("""
INSERT INTO permissions (id,code,description) VALUES
('42e79190-1d91-4f9a-b6e7-d1b1bc92d99f','onboarding.review','Review assigned onboarding
applications') ON CONFLICT (code) DO NOTHING
""")
    op.execute("""
INSERT INTO role_permissions (role_id,permission_id)
SELECT r.id,p.id FROM roles r CROSS JOIN permissions p
WHERE r.code IN ('TCG_ADMIN','TCG_LEGAL') AND p.code='onboarding.review'
ON CONFLICT DO NOTHING
""")
    op.execute("""
INSERT INTO onboarding_applications
(id,partner_id,applicant_id,status,revision,token_version,otp_attempts)
SELECT gen_random_uuid(),p.id,u.id,'DRAFT',1,1,0
FROM partners p JOIN users u ON u.partner_id=p.id AND
lower(u.email)=lower(p.primary_contact_email)
WHERE p.status='PENDING_APPROVAL' AND (
EXISTS (SELECT 1 FROM partner_capabilities pc JOIN partner_types pt ON pt.id=pc.capability_id
WHERE pc.partner_id=p.id AND pt.code IN ('RESELLER','REFERRAL'))
OR EXISTS (SELECT 1 FROM partner_types pt WHERE pt.id=p.partner_type_id AND pt.code IN
('RESELLER','REFERRAL')))
ON CONFLICT (partner_id) DO NOTHING
""")
    op.execute("""
UPDATE users SET is_active=false WHERE partner_id IN (SELECT partner_id FROM
onboarding_applications)
""")


def downgrade() -> None:
    raise RuntimeError("Onboarding holds verification records. Restore a reviewed backup instead.")
