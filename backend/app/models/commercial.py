from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Organization(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organizations"
    legal_name: Mapped[str] = mapped_column(String(200))
    identifier: Mapped[str] = mapped_column(String(200), unique=True)
    is_internal: Mapped[bool] = mapped_column(default=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")


class VendorProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "vendor_profiles"
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), unique=True)
    category: Mapped[str] = mapped_column(String(100))
    commercial_contact: Mapped[str] = mapped_column(String(320))


class PartnerAgreement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "partner_agreements"
    partner_id: Mapped[UUID] = mapped_column(ForeignKey("partners.id"), index=True)
    engagement_model: Mapped[str] = mapped_column(String(30))
    effective_from: Mapped[date] = mapped_column()
    effective_until: Mapped[date | None] = mapped_column(nullable=True)
    document_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="APPROVED", server_default="APPROVED")


class VendorAgreement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "vendor_agreements"
    provider_organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    buyer_organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    billing_basis: Mapped[str] = mapped_column(Text)
    charge_model: Mapped[str] = mapped_column(String(30))
    effective_from: Mapped[date] = mapped_column()
    effective_until: Mapped[date | None] = mapped_column(nullable=True)
    document_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    secret_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)


class OpportunityParticipant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "opportunity_participants"
    __table_args__ = (
        UniqueConstraint("opportunity_id", "organization_id", name="uq_opportunity_organization"),
        CheckConstraint("access_level IN ('NONE','PROGRESS','COMMERCIAL')", name="access_level"),
        CheckConstraint(
            "capability IS NULL OR capability IN ('RESELLER','REFERRAL','SYSTEM_INTEGRATOR')",
            name="capability",
        ),
    )
    opportunity_id: Mapped[UUID] = mapped_column(ForeignKey("opportunities.id"), index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    capability: Mapped[str | None] = mapped_column(String(30), nullable=True)
    access_level: Mapped[str] = mapped_column(String(20), default="NONE", server_default="NONE")
    active: Mapped[bool] = mapped_column(default=True, server_default="true")


class OpportunityRole(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "opportunity_role_assignments"
    __table_args__ = (
        UniqueConstraint(
            "opportunity_id",
            "participant_id",
            "role",
            "scope",
            name="uq_opportunity_role_participant",
        ),
        Index(
            "uq_primary_opportunity_role",
            "opportunity_id",
            "role",
            "scope",
            unique=True,
            postgresql_where=text("is_primary"),
        ),
    )
    opportunity_id: Mapped[UUID] = mapped_column(ForeignKey("opportunities.id"), index=True)
    participant_id: Mapped[UUID] = mapped_column(ForeignKey("opportunity_participants.id"))
    role: Mapped[str] = mapped_column(String(40))
    scope: Mapped[str] = mapped_column(String(100), default="OPPORTUNITY")
    is_primary: Mapped[bool] = mapped_column(default=True, server_default="true")


class SolutionComponent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "solution_components"
    __table_args__ = (CheckConstraint("amount >= 0", name="amount"),)
    opportunity_id: Mapped[UUID] = mapped_column(ForeignKey("opportunities.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    product_id: Mapped[UUID | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    sku_id: Mapped[UUID | None] = mapped_column(ForeignKey("skus.id"), nullable=True)
    external_service: Mapped[str | None] = mapped_column(String(200), nullable=True)
    owner_organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    seller_organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    delivery_organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    billing_organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))


class OpportunityVendorLink(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "opportunity_vendor_links"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="amount"),
        CheckConstraint("cost_treatment IN ('SEPARATE','POOL_DEDUCTION')", name="cost_treatment"),
    )
    opportunity_id: Mapped[UUID] = mapped_column(ForeignKey("opportunities.id"), index=True)
    agreement_id: Mapped[UUID] = mapped_column(ForeignKey("vendor_agreements.id"))
    component_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("solution_components.id"), nullable=True
    )
    payer_organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    usage_responsibility: Mapped[str] = mapped_column(Text)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    cost_treatment: Mapped[str] = mapped_column(String(30), default="SEPARATE")


class CommercialContract(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "commercial_contracts"
    __table_args__ = (
        CheckConstraint(
            "seller_organization_id <> buyer_organization_id", name="different_parties"
        ),
    )
    opportunity_id: Mapped[UUID] = mapped_column(ForeignKey("opportunities.id"), index=True)
    seller_organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    buyer_organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    kind: Mapped[str] = mapped_column(String(20))
    version: Mapped[int] = mapped_column(default=1, server_default="1")
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", server_default="DRAFT")
    document_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    accepted_quote_id: Mapped[UUID | None] = mapped_column(ForeignKey("quotes.id"), nullable=True)


class CommercialTermVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "commercial_term_versions"
    __table_args__ = (
        CheckConstraint(
            "engagement_model IN ('DIRECT','RESELLER','REFERRAL','SYSTEM_INTEGRATOR')",
            name="engagement_model",
        ),
        CheckConstraint("scope IN ('DEFAULT','PARTNER','OPPORTUNITY','CONTRACT')", name="scope"),
        CheckConstraint("status IN ('DRAFT','APPROVED','SUPERSEDED')", name="status"),
        CheckConstraint(
            "effective_until IS NULL OR effective_until >= effective_from", name="dates"
        ),
        CheckConstraint(
            "(scope='DEFAULT' AND partner_agreement_id IS NULL AND opportunity_id IS NULL "
            "AND contract_id IS NULL) OR "
            "(scope='PARTNER' AND partner_agreement_id IS NOT NULL AND opportunity_id IS NULL "
            "AND contract_id IS NULL) OR "
            "(scope='OPPORTUNITY' AND opportunity_id IS NOT NULL AND partner_agreement_id IS NULL "
            "AND contract_id IS NULL) OR "
            "(scope='CONTRACT' AND contract_id IS NOT NULL AND partner_agreement_id IS NULL "
            "AND opportunity_id IS NULL)",
            name="scope_identifier",
        ),
    )
    engagement_model: Mapped[str] = mapped_column(String(30), index=True)
    scope: Mapped[str] = mapped_column(String(20))
    partner_agreement_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("partner_agreements.id"), nullable=True
    )
    opportunity_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("opportunities.id"), nullable=True
    )
    contract_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("commercial_contracts.id"), nullable=True
    )
    sku_id: Mapped[UUID | None] = mapped_column(ForeignKey("skus.id"), nullable=True)
    effective_from: Mapped[date] = mapped_column()
    effective_until: Mapped[date | None] = mapped_column(nullable=True)
    supersedes_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("commercial_term_versions.id"), nullable=True
    )
    version: Mapped[int] = mapped_column(default=1, server_default="1")
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", server_default="DRAFT")
    parameters: Mapped[dict[str, object]] = mapped_column(JSONB)
    created_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class CommercialSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "commercial_snapshots"
    __table_args__ = (
        UniqueConstraint("quote_id", "revision", name="uq_commercial_quote_revision"),
    )
    opportunity_id: Mapped[UUID] = mapped_column(ForeignKey("opportunities.id"), index=True)
    quote_id: Mapped[UUID] = mapped_column(ForeignKey("quotes.id"))
    revision: Mapped[int] = mapped_column()
    engagement_version: Mapped[int] = mapped_column()
    payload: Mapped[dict[str, object]] = mapped_column(JSONB)


class ConversionEvidence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "conversion_evidence"
    opportunity_id: Mapped[UUID] = mapped_column(ForeignKey("opportunities.id"), unique=True)
    snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("commercial_snapshots.id"))
    evidence: Mapped[str] = mapped_column(Text)
    actual_eligibility: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    recorded_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))


class CommissionAccrual(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "commission_accruals"
    __table_args__ = (
        UniqueConstraint(
            "qualifying_event", "beneficiary_id", name="uq_commission_event_beneficiary"
        ),
        CheckConstraint("amount >= 0 AND eligible_amount >= 0", name="amount"),
        CheckConstraint("rate >= 0 AND rate <= 100", name="rate"),
    )
    opportunity_id: Mapped[UUID] = mapped_column(ForeignKey("opportunities.id"), index=True)
    snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("commercial_snapshots.id"))
    beneficiary_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    qualifying_event: Mapped[str] = mapped_column(String(200))
    eligible_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    rate: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    settlement_policy: Mapped[str | None] = mapped_column(Text, nullable=True)


class CommissionAdjustment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "commission_adjustments"
    __table_args__ = (UniqueConstraint("accrual_id", "event_key", name="uq_commission_adjustment"),)
    accrual_id: Mapped[UUID] = mapped_column(ForeignKey("commission_accruals.id"), index=True)
    event_key: Mapped[str] = mapped_column(String(200))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    reason: Mapped[str] = mapped_column(Text)
    created_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))


class CommissionPayment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "commission_payments"
    __table_args__ = (
        UniqueConstraint("accrual_id", "payment_reference", name="uq_commission_payment"),
        CheckConstraint("amount > 0", name="positive_amount"),
    )
    accrual_id: Mapped[UUID] = mapped_column(ForeignKey("commission_accruals.id"), index=True)
    payment_reference: Mapped[str] = mapped_column(String(200))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    recorded_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
