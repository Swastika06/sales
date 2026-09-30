from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SkuCategory(StrEnum):
    LICENSE = "LICENSE"
    IMPLEMENTATION = "IMPLEMENTATION"
    SERVICE = "SERVICE"
    OTHER = "OTHER"


class AdjustmentType(StrEnum):
    NONE = "NONE"
    PERCENT_DISCOUNT = "PERCENT_DISCOUNT"
    PERCENT_MARKUP = "PERCENT_MARKUP"
    REFERRAL_COMMISSION = "REFERRAL_COMMISSION"


class OverrideType(StrEnum):
    FIXED_PRICE = "FIXED_PRICE"
    PERCENT_DISCOUNT = "PERCENT_DISCOUNT"
    PERCENT_MARKUP = "PERCENT_MARKUP"


class Product(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "products"

    owner_organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True
    )
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true", index=True)

    skus: Mapped[list[Sku]] = relationship(
        back_populates="product", cascade="all, delete-orphan", lazy="selectin"
    )


class Sku(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "skus"
    __table_args__ = (
        CheckConstraint(
            "category IN ('LICENSE', 'IMPLEMENTATION', 'SERVICE', 'OTHER')",
            name="valid_category",
        ),
    )

    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(30), default=SkuCategory.LICENSE)
    unit: Mapped[str] = mapped_column(String(50), default="unit", server_default="unit")
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true", index=True)

    product: Mapped[Product] = relationship(back_populates="skus")
    prices: Mapped[list[ProductPrice]] = relationship(
        back_populates="sku", cascade="all, delete-orphan", lazy="selectin"
    )


class ProductPrice(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "product_prices"
    __table_args__ = (
        UniqueConstraint("sku_id", "effective_from", name="uq_product_prices_sku_effective"),
        CheckConstraint("amount >= 0", name="non_negative_amount"),
        CheckConstraint("currency = 'USD'", name="usd_currency"),
        CheckConstraint(
            "effective_until IS NULL OR effective_until >= effective_from",
            name="valid_effective_range",
        ),
    )

    sku_id: Mapped[UUID] = mapped_column(ForeignKey("skus.id", ondelete="CASCADE"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD")
    effective_from: Mapped[date] = mapped_column(index=True)
    effective_until: Mapped[date | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")

    sku: Mapped[Sku] = relationship(back_populates="prices")


class PartnerCommercialTerm(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "partner_commercial_terms"
    __table_args__ = (
        UniqueConstraint(
            "partner_type_id", "effective_from", name="uq_partner_terms_type_effective"
        ),
        CheckConstraint(
            "adjustment_type IN ('NONE', 'PERCENT_DISCOUNT', "
            "'PERCENT_MARKUP', 'REFERRAL_COMMISSION')",
            name="valid_adjustment_type",
        ),
        CheckConstraint("percentage >= 0 AND percentage <= 1000", name="valid_percentage"),
        CheckConstraint(
            "effective_until IS NULL OR effective_until >= effective_from",
            name="valid_effective_range",
        ),
    )

    partner_type_id: Mapped[UUID] = mapped_column(
        ForeignKey("partner_types.id", ondelete="CASCADE"), index=True
    )
    adjustment_type: Mapped[str] = mapped_column(String(30))
    percentage: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=Decimal("0"))
    effective_from: Mapped[date] = mapped_column(index=True)
    effective_until: Mapped[date | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")


class TierPricingAdjustment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tier_pricing_adjustments"
    __table_args__ = (
        UniqueConstraint("tier_id", "effective_from", name="uq_tier_adjustments_tier_effective"),
        CheckConstraint(
            "discount_percentage >= 0 AND discount_percentage <= 100",
            name="valid_discount_percentage",
        ),
        CheckConstraint(
            "effective_until IS NULL OR effective_until >= effective_from",
            name="valid_effective_range",
        ),
    )

    tier_id: Mapped[UUID] = mapped_column(
        ForeignKey("partner_tiers.id", ondelete="CASCADE"), index=True
    )
    discount_percentage: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=Decimal("0"))
    effective_from: Mapped[date] = mapped_column(index=True)
    effective_until: Mapped[date | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")


class PartnerPriceOverride(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "partner_price_overrides"
    __table_args__ = (
        UniqueConstraint(
            "partner_id", "sku_id", "effective_from", name="uq_partner_overrides_effective"
        ),
        CheckConstraint(
            "override_type IN ('FIXED_PRICE', 'PERCENT_DISCOUNT', 'PERCENT_MARKUP')",
            name="valid_override_type",
        ),
        CheckConstraint("value >= 0", name="non_negative_value"),
        CheckConstraint("currency = 'USD'", name="usd_currency"),
        CheckConstraint(
            "effective_until IS NULL OR effective_until >= effective_from",
            name="valid_effective_range",
        ),
    )

    partner_id: Mapped[UUID] = mapped_column(
        ForeignKey("partners.id", ondelete="CASCADE"), index=True
    )
    sku_id: Mapped[UUID] = mapped_column(ForeignKey("skus.id", ondelete="CASCADE"), index=True)
    override_type: Mapped[str] = mapped_column(String(30))
    value: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD")
    effective_from: Mapped[date] = mapped_column(index=True)
    effective_until: Mapped[date | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")
