from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DealApprovalStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class PipelineStage(StrEnum):
    REGISTERED = "REGISTERED"
    QUALIFIED = "QUALIFIED"
    DISCOVERY = "DISCOVERY"
    DEMO = "DEMO"
    POC = "POC"
    PROPOSAL = "PROPOSAL"
    NEGOTIATION = "NEGOTIATION"
    WON = "WON"
    LOST = "LOST"


class QuoteStatus(StrEnum):
    DRAFT = "DRAFT"
    UNDER_REVIEW = "UNDER_REVIEW"
    FINAL = "FINAL"
    ACCEPTED = "ACCEPTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class MafStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    RETURNED_FOR_CORRECTION = "RETURNED_FOR_CORRECTION"
    APPROVED = "APPROVED"
    ISSUED = "ISSUED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class OrderStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    RETURNED_FOR_CORRECTION = "RETURNED_FOR_CORRECTION"
    CONFIRMED = "CONFIRMED"
    PROVISIONING = "PROVISIONING"
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"


class Customer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customers"

    organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), index=True)
    legal_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country_code: Mapped[str] = mapped_column(String(2), index=True)
    contact_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    created_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))


class Opportunity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "opportunities"
    __table_args__ = (
        CheckConstraint(
            "engagement_model IS NULL OR engagement_model IN "
            "('DIRECT','RESELLER','REFERRAL','SYSTEM_INTEGRATOR')",
            name="engagement_model",
        ),
        CheckConstraint(
            "migration_review_required OR engagement_model IS NOT NULL",
            name="classified_engagement",
        ),
        CheckConstraint(
            "approval_status IN ('DRAFT', 'SUBMITTED', 'UNDER_REVIEW', 'APPROVED', 'REJECTED')",
            name="valid_approval_status",
        ),
        CheckConstraint(
            "stage IN ('REGISTERED', 'QUALIFIED', 'DISCOVERY', 'DEMO', 'POC', 'PROPOSAL', "
            "'NEGOTIATION', 'WON', 'LOST')",
            name="valid_stage",
        ),
        CheckConstraint("estimated_value >= 0", name="non_negative_estimated_value"),
        CheckConstraint(
            "actual_contract_value IS NULL OR actual_contract_value >= 0",
            name="non_negative_actual_value",
        ),
    )

    engagement_model: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    commercial_version: Mapped[int] = mapped_column(default=0, server_default="0")
    migration_review_required: Mapped[bool] = mapped_column(default=False, server_default="false")
    responsible_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reference: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    partner_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("partners.id", ondelete="RESTRICT"), index=True, nullable=True
    )
    customer_id: Mapped[UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), index=True
    )
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD")
    expected_close_date: Mapped[date | None] = mapped_column(nullable=True)
    approval_status: Mapped[str] = mapped_column(
        String(30), default=DealApprovalStatus.DRAFT, server_default="DRAFT", index=True
    )
    stage: Mapped[str] = mapped_column(
        String(30), default=PipelineStage.REGISTERED, server_default="REGISTERED", index=True
    )
    review_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    protection_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    actual_contract_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    actual_close_date: Mapped[date | None] = mapped_column(nullable=True)
    lost_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    reviewed_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    customer: Mapped[Customer] = relationship(lazy="joined")
    stage_history: Mapped[list[OpportunityStageHistory]] = relationship(
        back_populates="opportunity",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="OpportunityStageHistory.changed_at",
    )


class OpportunityStageHistory(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "opportunity_stage_history"

    opportunity_id: Mapped[UUID] = mapped_column(
        ForeignKey("opportunities.id", ondelete="CASCADE"), index=True
    )
    from_stage: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_stage: Mapped[str] = mapped_column(String(30))
    note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    changed_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    opportunity: Mapped[Opportunity] = relationship(back_populates="stage_history")


class StoredAttachment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "stored_attachments"

    owner_type: Mapped[str] = mapped_column(String(30), index=True)
    owner_id: Mapped[UUID] = mapped_column(index=True)
    kind: Mapped[str] = mapped_column(String(50), default="SUPPORTING")
    object_key: Mapped[str] = mapped_column(String(700), unique=True)
    file_name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(150))
    size_bytes: Mapped[int] = mapped_column()
    checksum_sha256: Mapped[str] = mapped_column(String(64))
    uploaded_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))


class Quote(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "quotes"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT', 'UNDER_REVIEW', 'FINAL', 'ACCEPTED', 'EXPIRED', 'CANCELLED')",
            name="valid_status",
        ),
        CheckConstraint("subtotal >= 0 AND discount_total >= 0 AND total >= 0", name="amounts"),
    )

    reference: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    opportunity_id: Mapped[UUID] = mapped_column(
        ForeignKey("opportunities.id", ondelete="RESTRICT"), index=True
    )
    partner_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("partners.id", ondelete="RESTRICT"), index=True, nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(30), default=QuoteStatus.DRAFT, server_default="DRAFT", index=True
    )
    contract_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("commercial_contracts.id", use_alter=True), nullable=True
    )
    commercial_model: Mapped[str] = mapped_column(String(50), default="RESELLER")
    valid_until: Mapped[date | None] = mapped_column(nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    discount_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    current_revision: Mapped[int] = mapped_column(default=0, server_default="0")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))

    items: Mapped[list[QuoteItem]] = relationship(
        back_populates="quote", cascade="all, delete-orphan", lazy="selectin"
    )
    revisions: Mapped[list[QuoteRevision]] = relationship(
        back_populates="quote", cascade="all, delete-orphan", lazy="selectin"
    )


class QuoteItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "quote_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="positive_quantity"),
        CheckConstraint("unit_price >= 0 AND line_total >= 0", name="non_negative_amounts"),
        CheckConstraint("discount_percentage >= 0 AND discount_percentage <= 100", name="discount"),
    )

    quote_id: Mapped[UUID] = mapped_column(ForeignKey("quotes.id", ondelete="CASCADE"), index=True)
    sku_id: Mapped[UUID] = mapped_column(ForeignKey("skus.id", ondelete="RESTRICT"))
    sku_code: Mapped[str] = mapped_column(String(80))
    sku_name: Mapped[str] = mapped_column(String(150))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    discount_percentage: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=Decimal("0"))
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    pricing_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB)

    quote: Mapped[Quote] = relationship(back_populates="items")


class QuoteRevision(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "quote_revisions"
    __table_args__ = (UniqueConstraint("quote_id", "revision_number", name="uq_quote_revision"),)

    quote_id: Mapped[UUID] = mapped_column(ForeignKey("quotes.id", ondelete="CASCADE"), index=True)
    revision_number: Mapped[int] = mapped_column()
    snapshot: Mapped[dict[str, object]] = mapped_column(JSONB)
    created_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    quote: Mapped[Quote] = relationship(back_populates="revisions")


class MafRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "maf_requests"

    reference: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    opportunity_id: Mapped[UUID] = mapped_column(
        ForeignKey("opportunities.id", ondelete="RESTRICT"), index=True
    )
    partner_id: Mapped[UUID] = mapped_column(
        ForeignKey("partners.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(40), default=MafStatus.DRAFT, index=True)
    tender_reference: Mapped[str] = mapped_column(String(150))
    tender_authority: Mapped[str] = mapped_column(String(200))
    tender_due_date: Mapped[date] = mapped_column()
    tender_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    reviewed_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class Order(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "orders"

    reference: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    quote_id: Mapped[UUID] = mapped_column(
        ForeignKey("quotes.id", ondelete="RESTRICT"), unique=True, index=True
    )
    partner_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("partners.id", ondelete="RESTRICT"), index=True, nullable=True
    )
    status: Mapped[str] = mapped_column(String(40), default=OrderStatus.DRAFT, index=True)
    billing_name: Mapped[str] = mapped_column(String(200))
    billing_address: Mapped[str] = mapped_column(Text)
    billing_email: Mapped[str] = mapped_column(String(320))
    currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD")
    total: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    quote_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB)
    review_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    reviewed_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    status_history: Mapped[list[OrderStatusHistory]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="OrderStatusHistory.changed_at",
    )


class OrderStatusHistory(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "order_status_history"

    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    to_status: Mapped[str] = mapped_column(String(40))
    note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    changed_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    order: Mapped[Order] = relationship(back_populates="status_history")


class DomainEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "domain_events"

    event_type: Mapped[str] = mapped_column(String(100), index=True)
    aggregate_type: Mapped[str] = mapped_column(String(50))
    aggregate_id: Mapped[UUID] = mapped_column(index=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
