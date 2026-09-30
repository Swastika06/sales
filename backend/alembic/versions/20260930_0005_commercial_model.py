"""Add engagement commercials without rewriting finalized history.

Legacy tier tables are retained only for historical foreign keys. Downgrade is
intentionally blocked because removing new commercials would destroy financial history.
"""

from alembic import op

revision = "20260930_0005"
down_revision = "20260923_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE organizations (
        legal_name VARCHAR(200) NOT NULL,
        identifier VARCHAR(200) NOT NULL,
        is_internal BOOLEAN DEFAULT 'false' NOT NULL,
        is_active BOOLEAN DEFAULT 'true' NOT NULL,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        CONSTRAINT pk_organizations PRIMARY KEY (id),
        CONSTRAINT uq_organizations_identifier UNIQUE (identifier)
        )
    """)
    op.execute("""
        CREATE TABLE partner_capabilities (
        partner_id UUID NOT NULL,
        capability_id UUID NOT NULL,
        CONSTRAINT pk_partner_capabilities PRIMARY KEY (partner_id, capability_id),
        CONSTRAINT fk_partner_capabilities_partner_id_partners FOREIGN KEY(partner_id)
        REFERENCES partners (id) ON DELETE CASCADE,
        CONSTRAINT fk_partner_capabilities_capability_id_partner_types FOREIGN
        KEY(capability_id) REFERENCES partner_types (id) ON DELETE RESTRICT
        )
    """)
    op.execute("""
        CREATE TABLE vendor_profiles (
        organization_id UUID NOT NULL,
        category VARCHAR(100) NOT NULL,
        commercial_contact VARCHAR(320) NOT NULL,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        CONSTRAINT pk_vendor_profiles PRIMARY KEY (id),
        CONSTRAINT uq_vendor_profiles_organization_id UNIQUE (organization_id),
        CONSTRAINT fk_vendor_profiles_organization_id_organizations FOREIGN KEY(organization_id)
        REFERENCES organizations (id)
        )
    """)
    op.execute("""
        CREATE TABLE opportunity_participants (
        opportunity_id UUID NOT NULL,
        organization_id UUID NOT NULL,
        capability VARCHAR(30),
        access_level VARCHAR(20) DEFAULT 'NONE' NOT NULL,
        active BOOLEAN DEFAULT 'true' NOT NULL,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        CONSTRAINT pk_opportunity_participants PRIMARY KEY (id),
        CONSTRAINT uq_opportunity_organization UNIQUE (opportunity_id, organization_id),
        CONSTRAINT ck_opportunity_participants_access_level CHECK (access_level IN
        ('NONE','PROGRESS','COMMERCIAL')),
        CONSTRAINT ck_opportunity_participants_capability CHECK (capability IS NULL OR
        capability IN ('RESELLER','REFERRAL','SYSTEM_INTEGRATOR')),
        CONSTRAINT fk_opportunity_participants_opportunity_id_opportunities FOREIGN
        KEY(opportunity_id) REFERENCES opportunities (id),
        CONSTRAINT fk_opportunity_participants_organization_id_organizations FOREIGN
        KEY(organization_id) REFERENCES organizations (id)
        )
    """)
    op.execute("""
        CREATE INDEX ix_opportunity_participants_opportunity_id ON opportunity_participants
        (opportunity_id)
    """)
    op.execute("""
        CREATE INDEX ix_opportunity_participants_organization_id ON opportunity_participants
        (organization_id)
    """)
    op.execute("""
        CREATE TABLE partner_agreements (
        partner_id UUID NOT NULL,
        engagement_model VARCHAR(30) NOT NULL,
        effective_from DATE NOT NULL,
        effective_until DATE,
        document_id UUID,
        status VARCHAR(20) DEFAULT 'APPROVED' NOT NULL,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        CONSTRAINT pk_partner_agreements PRIMARY KEY (id),
        CONSTRAINT fk_partner_agreements_partner_id_partners FOREIGN KEY(partner_id) REFERENCES
        partners (id),
        CONSTRAINT fk_partner_agreements_document_id_documents FOREIGN KEY(document_id)
        REFERENCES documents (id)
        )
    """)
    op.execute("""
        CREATE INDEX ix_partner_agreements_partner_id ON partner_agreements (partner_id)
    """)
    op.execute("""
        CREATE TABLE solution_components (
        opportunity_id UUID NOT NULL,
        name VARCHAR(200) NOT NULL,
        product_id UUID,
        sku_id UUID,
        external_service VARCHAR(200),
        owner_organization_id UUID NOT NULL,
        seller_organization_id UUID NOT NULL,
        delivery_organization_id UUID NOT NULL,
        billing_organization_id UUID NOT NULL,
        amount NUMERIC(18, 2) NOT NULL,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        CONSTRAINT pk_solution_components PRIMARY KEY (id),
        CONSTRAINT ck_solution_components_amount CHECK (amount >= 0),
        CONSTRAINT fk_solution_components_opportunity_id_opportunities FOREIGN
        KEY(opportunity_id) REFERENCES opportunities (id),
        CONSTRAINT fk_solution_components_product_id_products FOREIGN KEY(product_id) REFERENCES
        products (id),
        CONSTRAINT fk_solution_components_sku_id_skus FOREIGN KEY(sku_id) REFERENCES skus (id),
        CONSTRAINT fk_solution_components_owner_organization_id_organizations FOREIGN
        KEY(owner_organization_id) REFERENCES organizations (id),
        CONSTRAINT fk_solution_components_seller_organization_id_organizations FOREIGN
        KEY(seller_organization_id) REFERENCES organizations (id),
        CONSTRAINT fk_solution_components_delivery_organization_id_organizations FOREIGN
        KEY(delivery_organization_id) REFERENCES organizations (id),
        CONSTRAINT fk_solution_components_billing_organization_id_organizations FOREIGN
        KEY(billing_organization_id) REFERENCES organizations (id)
        )
    """)
    op.execute("""
        CREATE INDEX ix_solution_components_opportunity_id ON solution_components
        (opportunity_id)
    """)
    op.execute("""
        CREATE TABLE vendor_agreements (
        provider_organization_id UUID NOT NULL,
        buyer_organization_id UUID NOT NULL,
        billing_basis TEXT NOT NULL,
        charge_model VARCHAR(30) NOT NULL,
        effective_from DATE NOT NULL,
        effective_until DATE,
        document_id UUID,
        secret_reference VARCHAR(500),
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        CONSTRAINT pk_vendor_agreements PRIMARY KEY (id),
        CONSTRAINT fk_vendor_agreements_provider_organization_id_organizations FOREIGN
        KEY(provider_organization_id) REFERENCES organizations (id),
        CONSTRAINT fk_vendor_agreements_buyer_organization_id_organizations FOREIGN
        KEY(buyer_organization_id) REFERENCES organizations (id),
        CONSTRAINT fk_vendor_agreements_document_id_documents FOREIGN KEY(document_id)
        REFERENCES documents (id)
        )
    """)
    op.execute("""
        CREATE TABLE commercial_contracts (
        opportunity_id UUID NOT NULL,
        seller_organization_id UUID NOT NULL,
        buyer_organization_id UUID NOT NULL,
        kind VARCHAR(20) NOT NULL,
        version INTEGER DEFAULT '1' NOT NULL,
        status VARCHAR(20) DEFAULT 'DRAFT' NOT NULL,
        document_id UUID,
        accepted_quote_id UUID,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        CONSTRAINT pk_commercial_contracts PRIMARY KEY (id),
        CONSTRAINT ck_commercial_contracts_different_parties CHECK (seller_organization_id <>
        buyer_organization_id),
        CONSTRAINT fk_commercial_contracts_opportunity_id_opportunities FOREIGN
        KEY(opportunity_id) REFERENCES opportunities (id),
        CONSTRAINT fk_commercial_contracts_seller_organization_id_organizations FOREIGN
        KEY(seller_organization_id) REFERENCES organizations (id),
        CONSTRAINT fk_commercial_contracts_buyer_organization_id_organizations FOREIGN
        KEY(buyer_organization_id) REFERENCES organizations (id),
        CONSTRAINT fk_commercial_contracts_document_id_documents FOREIGN KEY(document_id)
        REFERENCES documents (id),
        CONSTRAINT fk_commercial_contracts_accepted_quote_id_quotes FOREIGN
        KEY(accepted_quote_id) REFERENCES quotes (id)
        )
    """)
    op.execute("""
        CREATE INDEX ix_commercial_contracts_opportunity_id ON commercial_contracts
        (opportunity_id)
    """)
    op.execute("""
        CREATE TABLE commercial_snapshots (
        opportunity_id UUID NOT NULL,
        quote_id UUID NOT NULL,
        revision INTEGER NOT NULL,
        engagement_version INTEGER NOT NULL,
        payload JSONB NOT NULL,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        CONSTRAINT pk_commercial_snapshots PRIMARY KEY (id),
        CONSTRAINT uq_commercial_quote_revision UNIQUE (quote_id, revision),
        CONSTRAINT fk_commercial_snapshots_opportunity_id_opportunities FOREIGN
        KEY(opportunity_id) REFERENCES opportunities (id),
        CONSTRAINT fk_commercial_snapshots_quote_id_quotes FOREIGN KEY(quote_id) REFERENCES
        quotes (id)
        )
    """)
    op.execute("""
        CREATE INDEX ix_commercial_snapshots_opportunity_id ON commercial_snapshots
        (opportunity_id)
    """)
    op.execute("""
        CREATE TABLE opportunity_role_assignments (
        opportunity_id UUID NOT NULL,
        participant_id UUID NOT NULL,
        role VARCHAR(40) NOT NULL,
        scope VARCHAR(100) NOT NULL,
        is_primary BOOLEAN DEFAULT 'true' NOT NULL,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        CONSTRAINT pk_opportunity_role_assignments PRIMARY KEY (id),
        CONSTRAINT uq_opportunity_role_participant UNIQUE (opportunity_id, participant_id, role,
        scope),
        CONSTRAINT fk_opportunity_role_assignments_opportunity_id_opportunities FOREIGN
        KEY(opportunity_id) REFERENCES opportunities (id),
        CONSTRAINT fk_opportunity_role_assignments_participant_id_opportun_c088 FOREIGN
        KEY(participant_id) REFERENCES opportunity_participants (id)
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_primary_opportunity_role ON opportunity_role_assignments
        (opportunity_id, role, scope) WHERE is_primary
    """)
    op.execute("""
        CREATE INDEX ix_opportunity_role_assignments_opportunity_id ON
        opportunity_role_assignments (opportunity_id)
    """)
    op.execute("""
        CREATE TABLE opportunity_vendor_links (
        opportunity_id UUID NOT NULL,
        agreement_id UUID NOT NULL,
        component_id UUID,
        payer_organization_id UUID NOT NULL,
        usage_responsibility TEXT NOT NULL,
        amount NUMERIC(18, 2) NOT NULL,
        cost_treatment VARCHAR(30) NOT NULL,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        CONSTRAINT pk_opportunity_vendor_links PRIMARY KEY (id),
        CONSTRAINT ck_opportunity_vendor_links_amount CHECK (amount >= 0),
        CONSTRAINT ck_opportunity_vendor_links_cost_treatment CHECK (cost_treatment IN
        ('SEPARATE','POOL_DEDUCTION')),
        CONSTRAINT fk_opportunity_vendor_links_opportunity_id_opportunities FOREIGN
        KEY(opportunity_id) REFERENCES opportunities (id),
        CONSTRAINT fk_opportunity_vendor_links_agreement_id_vendor_agreements FOREIGN
        KEY(agreement_id) REFERENCES vendor_agreements (id),
        CONSTRAINT fk_opportunity_vendor_links_component_id_solution_components FOREIGN
        KEY(component_id) REFERENCES solution_components (id),
        CONSTRAINT fk_opportunity_vendor_links_payer_organization_id_organizations FOREIGN
        KEY(payer_organization_id) REFERENCES organizations (id)
        )
    """)
    op.execute("""
        CREATE INDEX ix_opportunity_vendor_links_opportunity_id ON opportunity_vendor_links
        (opportunity_id)
    """)
    op.execute("""
        CREATE TABLE commercial_term_versions (
        engagement_model VARCHAR(30) NOT NULL,
        scope VARCHAR(20) NOT NULL,
        partner_agreement_id UUID,
        opportunity_id UUID,
        contract_id UUID,
        sku_id UUID,
        effective_from DATE NOT NULL,
        effective_until DATE,
        supersedes_id UUID,
        version INTEGER DEFAULT '1' NOT NULL,
        status VARCHAR(20) DEFAULT 'DRAFT' NOT NULL,
        parameters JSONB NOT NULL,
        created_by_id UUID,
        approved_by_id UUID,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        CONSTRAINT pk_commercial_term_versions PRIMARY KEY (id),
        CONSTRAINT ck_commercial_term_versions_engagement_model CHECK (engagement_model IN
        ('DIRECT','RESELLER','REFERRAL','SYSTEM_INTEGRATOR')),
        CONSTRAINT ck_commercial_term_versions_scope CHECK (scope IN
        ('DEFAULT','PARTNER','OPPORTUNITY','CONTRACT')),
        CONSTRAINT ck_commercial_term_versions_status CHECK (status IN
        ('DRAFT','APPROVED','SUPERSEDED')),
        CONSTRAINT ck_commercial_term_versions_dates CHECK (effective_until IS NULL OR
        effective_until >= effective_from),
        CONSTRAINT ck_commercial_term_versions_scope_identifier CHECK ((scope='DEFAULT' AND
        partner_agreement_id IS NULL AND opportunity_id IS NULL AND contract_id IS NULL) OR
        (scope='PARTNER' AND partner_agreement_id IS NOT NULL AND opportunity_id IS NULL AND
        contract_id IS NULL) OR (scope='OPPORTUNITY' AND opportunity_id IS NOT NULL AND
        partner_agreement_id IS NULL AND contract_id IS NULL) OR (scope='CONTRACT' AND
        contract_id IS NOT NULL AND partner_agreement_id IS NULL AND opportunity_id IS NULL)),
        CONSTRAINT fk_commercial_term_versions_partner_agreement_id_partne_08af FOREIGN
        KEY(partner_agreement_id) REFERENCES partner_agreements (id),
        CONSTRAINT fk_commercial_term_versions_opportunity_id_opportunities FOREIGN
        KEY(opportunity_id) REFERENCES opportunities (id),
        CONSTRAINT fk_commercial_term_versions_contract_id_commercial_contracts FOREIGN
        KEY(contract_id) REFERENCES commercial_contracts (id),
        CONSTRAINT fk_commercial_term_versions_sku_id_skus FOREIGN KEY(sku_id) REFERENCES skus
        (id),
        CONSTRAINT fk_commercial_term_versions_supersedes_id_commercial_te_6d6a FOREIGN
        KEY(supersedes_id) REFERENCES commercial_term_versions (id),
        CONSTRAINT fk_commercial_term_versions_created_by_id_users FOREIGN KEY(created_by_id)
        REFERENCES users (id),
        CONSTRAINT fk_commercial_term_versions_approved_by_id_users FOREIGN KEY(approved_by_id)
        REFERENCES users (id)
        )
    """)
    op.execute("""
        CREATE INDEX ix_commercial_term_versions_engagement_model ON commercial_term_versions
        (engagement_model)
    """)
    op.execute("""
        CREATE TABLE commission_accruals (
        opportunity_id UUID NOT NULL,
        snapshot_id UUID NOT NULL,
        beneficiary_id UUID NOT NULL,
        qualifying_event VARCHAR(200) NOT NULL,
        eligible_amount NUMERIC(18, 2) NOT NULL,
        rate NUMERIC(9, 6) NOT NULL,
        amount NUMERIC(18, 2) NOT NULL,
        settlement_policy TEXT,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        CONSTRAINT pk_commission_accruals PRIMARY KEY (id),
        CONSTRAINT uq_commission_event_beneficiary UNIQUE (qualifying_event, beneficiary_id),
        CONSTRAINT ck_commission_accruals_amount CHECK (amount >= 0 AND eligible_amount >= 0),
        CONSTRAINT ck_commission_accruals_rate CHECK (rate >= 0 AND rate <= 100),
        CONSTRAINT fk_commission_accruals_opportunity_id_opportunities FOREIGN
        KEY(opportunity_id) REFERENCES opportunities (id),
        CONSTRAINT fk_commission_accruals_snapshot_id_commercial_snapshots FOREIGN
        KEY(snapshot_id) REFERENCES commercial_snapshots (id),
        CONSTRAINT fk_commission_accruals_beneficiary_id_organizations FOREIGN
        KEY(beneficiary_id) REFERENCES organizations (id)
        )
    """)
    op.execute("""
        CREATE INDEX ix_commission_accruals_opportunity_id ON commission_accruals
        (opportunity_id)
    """)
    op.execute("""
        CREATE INDEX ix_commission_accruals_beneficiary_id ON commission_accruals
        (beneficiary_id)
    """)
    op.execute("""
        CREATE TABLE conversion_evidence (
        opportunity_id UUID NOT NULL,
        snapshot_id UUID NOT NULL,
        evidence TEXT NOT NULL,
        actual_eligibility JSONB,
        recorded_by_id UUID NOT NULL,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        CONSTRAINT pk_conversion_evidence PRIMARY KEY (id),
        CONSTRAINT uq_conversion_evidence_opportunity_id UNIQUE (opportunity_id),
        CONSTRAINT fk_conversion_evidence_opportunity_id_opportunities FOREIGN
        KEY(opportunity_id) REFERENCES opportunities (id),
        CONSTRAINT fk_conversion_evidence_snapshot_id_commercial_snapshots FOREIGN
        KEY(snapshot_id) REFERENCES commercial_snapshots (id),
        CONSTRAINT fk_conversion_evidence_recorded_by_id_users FOREIGN KEY(recorded_by_id)
        REFERENCES users (id)
        )
    """)
    op.execute("""
        CREATE TABLE commission_adjustments (
        accrual_id UUID NOT NULL,
        event_key VARCHAR(200) NOT NULL,
        amount NUMERIC(18, 2) NOT NULL,
        reason TEXT NOT NULL,
        created_by_id UUID NOT NULL,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        CONSTRAINT pk_commission_adjustments PRIMARY KEY (id),
        CONSTRAINT uq_commission_adjustment UNIQUE (accrual_id, event_key),
        CONSTRAINT fk_commission_adjustments_accrual_id_commission_accruals FOREIGN
        KEY(accrual_id) REFERENCES commission_accruals (id),
        CONSTRAINT fk_commission_adjustments_created_by_id_users FOREIGN KEY(created_by_id)
        REFERENCES users (id)
        )
    """)
    op.execute("""
        CREATE INDEX ix_commission_adjustments_accrual_id ON commission_adjustments (accrual_id)
    """)
    op.execute("""
        CREATE TABLE commission_payments (
        accrual_id UUID NOT NULL,
        payment_reference VARCHAR(200) NOT NULL,
        amount NUMERIC(18, 2) NOT NULL,
        recorded_by_id UUID NOT NULL,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        CONSTRAINT pk_commission_payments PRIMARY KEY (id),
        CONSTRAINT uq_commission_payment UNIQUE (accrual_id, payment_reference),
        CONSTRAINT ck_commission_payments_positive_amount CHECK (amount > 0),
        CONSTRAINT fk_commission_payments_accrual_id_commission_accruals FOREIGN KEY(accrual_id)
        REFERENCES commission_accruals (id),
        CONSTRAINT fk_commission_payments_recorded_by_id_users FOREIGN KEY(recorded_by_id)
        REFERENCES users (id)
        )
    """)
    op.execute("""
        CREATE INDEX ix_commission_payments_accrual_id ON commission_payments (accrual_id)
    """)

    op.execute("""
        ALTER TABLE partners ADD COLUMN organization_id UUID REFERENCES organizations(id)
    """)
    op.execute("""
        ALTER TABLE partners ADD CONSTRAINT uq_partner_organization UNIQUE (organization_id)
    """)
    op.execute("""
        ALTER TABLE customers ADD COLUMN organization_id UUID REFERENCES organizations(id)
    """)
    op.execute("""
        CREATE INDEX ix_customers_organization_id ON customers(organization_id)
    """)
    op.execute("""
        ALTER TABLE products ADD COLUMN owner_organization_id UUID REFERENCES organizations(id)
    """)
    op.execute("""
        ALTER TABLE opportunities ALTER COLUMN partner_id DROP NOT NULL
    """)
    op.execute("""
        ALTER TABLE quotes ALTER COLUMN partner_id DROP NOT NULL
    """)
    op.execute("""
        ALTER TABLE orders ALTER COLUMN partner_id DROP NOT NULL
    """)
    op.execute("""
        ALTER TABLE opportunities ADD COLUMN engagement_model VARCHAR(30)
    """)
    op.execute("""
        ALTER TABLE opportunities ADD COLUMN commercial_version INTEGER NOT NULL DEFAULT 0
    """)
    op.execute("""
        ALTER TABLE opportunities ADD COLUMN migration_review_required BOOLEAN NOT NULL DEFAULT
        true
    """)
    op.execute("""
        ALTER TABLE opportunities ADD COLUMN responsible_user_id UUID REFERENCES users(id)
    """)
    op.execute("""
        ALTER TABLE opportunities ADD CONSTRAINT ck_opportunities_engagement_model
        CHECK (engagement_model IS NULL OR engagement_model IN
        ('DIRECT','RESELLER','REFERRAL','SYSTEM_INTEGRATOR'))
    """)
    op.execute("""
        ALTER TABLE opportunities ADD CONSTRAINT ck_opportunities_classified_engagement
        CHECK (migration_review_required OR engagement_model IS NOT NULL)
    """)
    op.execute("""
        CREATE INDEX ix_opportunities_engagement_model ON opportunities(engagement_model)
    """)
    op.execute("""
        ALTER TABLE quotes ADD COLUMN contract_id UUID REFERENCES commercial_contracts(id)
    """)
    op.execute("""
        INSERT INTO organizations (id, legal_name, identifier, is_internal)
        VALUES ('00000000-0000-0000-0000-000000000001','TCG Digital','TCG_INTERNAL',true)
    """)
    op.execute("""
        INSERT INTO organizations (id, legal_name, identifier)
        SELECT id, COALESCE(legal_name,company_name), 'partner:' || id::text FROM partners
    """)
    op.execute("""
        UPDATE partners SET organization_id=id
    """)
    op.execute("""
        INSERT INTO organizations (id, legal_name, identifier)
        SELECT id, COALESCE(legal_name,name), 'customer:' || id::text FROM customers
    """)
    op.execute("""
        UPDATE customers SET organization_id=id
    """)
    op.execute("""
        UPDATE products SET owner_organization_id='00000000-0000-0000-0000-000000000001'
        WHERE code='MCUBE'
    """)
    op.execute("""
        INSERT INTO partner_capabilities (partner_id,capability_id)
        SELECT id,partner_type_id FROM partners
    """)
    op.execute("""
        UPDATE opportunities o SET engagement_model=e.model
        FROM (SELECT opportunity_id, MIN(commercial_model) AS model FROM quotes
        GROUP BY opportunity_id
        HAVING COUNT(DISTINCT commercial_model)=1
        AND MIN(commercial_model) IN
        ('DIRECT','RESELLER','REFERRAL','SYSTEM_INTEGRATOR')) e
        WHERE o.id=e.opportunity_id
    """)
    op.execute("""
        INSERT INTO opportunity_participants
        (id,opportunity_id,organization_id,capability,access_level,active)
        SELECT gen_random_uuid(),o.id,p.organization_id,
        CASE WHEN o.engagement_model IN ('RESELLER','REFERRAL','SYSTEM_INTEGRATOR')
        THEN o.engagement_model ELSE NULL END,
        CASE WHEN o.engagement_model IN ('RESELLER','SYSTEM_INTEGRATOR')
        THEN 'COMMERCIAL' ELSE 'PROGRESS' END,true
        FROM opportunities o JOIN partners p ON o.partner_id=p.id
    """)
    op.execute("""
        INSERT INTO opportunity_participants
        (id,opportunity_id,organization_id,access_level,active)
        SELECT gen_random_uuid(),id,'00000000-0000-0000-0000-000000000001','NONE',true
        FROM opportunities
    """)
    op.execute("""
        INSERT INTO opportunity_participants
        (id,opportunity_id,organization_id,access_level,active)
        SELECT gen_random_uuid(),o.id,c.organization_id,'NONE',true
        FROM opportunities o JOIN customers c ON o.customer_id=c.id
        ON CONFLICT (opportunity_id,organization_id) DO NOTHING
    """)
    op.execute("""
        UPDATE documents SET visibility='TCG_INTERNAL' WHERE visibility='PARTNER_TIER'
    """)
    op.execute("""
        UPDATE partner_tiers SET is_active=false
    """)
    op.execute("""
        UPDATE tier_pricing_adjustments SET is_active=false
    """)
    op.execute("""
        INSERT INTO commercial_term_versions
        (id,engagement_model,scope,effective_from,status,parameters,version)
        VALUES ('00000000-0000-0000-0000-000000000010','REFERRAL','DEFAULT',
        '2026-09-28','APPROVED','{"referral_rate":"10"}',1)
    """)
    op.execute("ALTER TABLE opportunities ALTER COLUMN migration_review_required SET DEFAULT false")
    # Retired legacy commercial rows remain untouched for audit/review, but the
    # resolver never reads them. The database enforces snapshot and ledger immutability.
    op.execute("""
        CREATE FUNCTION commercial_prevent_mutation() RETURNS trigger AS $$
        BEGIN
        RAISE EXCEPTION 'Financial history is immutable; create an amendment or adjustment';
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER immutable_commercial_snapshot BEFORE UPDATE OR DELETE ON
        commercial_snapshots
        FOR EACH ROW EXECUTE FUNCTION commercial_prevent_mutation()
    """)
    op.execute("""
        CREATE TRIGGER immutable_quote_revision BEFORE UPDATE OR DELETE ON quote_revisions
        FOR EACH ROW EXECUTE FUNCTION commercial_prevent_mutation()
    """)
    op.execute("""
        CREATE TRIGGER immutable_accrual BEFORE UPDATE OR DELETE ON commission_accruals
        FOR EACH ROW EXECUTE FUNCTION commercial_prevent_mutation()
    """)
    op.execute("""
        CREATE TRIGGER immutable_adjustment BEFORE UPDATE OR DELETE ON commission_adjustments
        FOR EACH ROW EXECUTE FUNCTION commercial_prevent_mutation()
    """)
    op.execute("""
        CREATE TRIGGER immutable_payment BEFORE UPDATE OR DELETE ON commission_payments
        FOR EACH ROW EXECUTE FUNCTION commercial_prevent_mutation()
    """)
    op.execute("""
        CREATE TRIGGER immutable_conversion BEFORE UPDATE OR DELETE ON conversion_evidence
        FOR EACH ROW EXECUTE FUNCTION commercial_prevent_mutation()
    """)
    op.execute("""
        CREATE FUNCTION commercial_protect_terms() RETURNS trigger AS $$
        BEGIN
        IF OLD.status IN ('APPROVED','SUPERSEDED') AND (
        TG_OP='DELETE' OR NEW.parameters IS DISTINCT FROM OLD.parameters
        OR NEW.engagement_model IS DISTINCT FROM OLD.engagement_model
        OR NEW.scope IS DISTINCT FROM OLD.scope
        OR NEW.partner_agreement_id IS DISTINCT FROM OLD.partner_agreement_id
        OR NEW.opportunity_id IS DISTINCT FROM OLD.opportunity_id
        OR NEW.contract_id IS DISTINCT FROM OLD.contract_id
        OR NEW.sku_id IS DISTINCT FROM OLD.sku_id
        OR NEW.effective_from IS DISTINCT FROM OLD.effective_from
        OR NEW.version IS DISTINCT FROM OLD.version
        OR NEW.status='DRAFT'
        ) THEN RAISE EXCEPTION 'Approved commercial terms require a new version';
        END IF;
        IF TG_OP='DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER immutable_approved_terms BEFORE UPDATE OR DELETE ON
        commercial_term_versions
        FOR EACH ROW EXECUTE FUNCTION commercial_protect_terms()
    """)


def downgrade() -> None:
    raise RuntimeError("Restore a verified backup; commercial financial history cannot be dropped.")
