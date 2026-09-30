from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.identity import User


class PartnerStatus(StrEnum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"
    SUSPENDED = "SUSPENDED"
    INACTIVE = "INACTIVE"


partner_countries = Table(
    "partner_countries",
    Base.metadata,
    Column("partner_id", ForeignKey("partners.id", ondelete="CASCADE"), primary_key=True),
    Column("country_id", ForeignKey("countries.id", ondelete="RESTRICT"), primary_key=True),
)


partner_capabilities = Table(
    "partner_capabilities",
    Base.metadata,
    Column("partner_id", ForeignKey("partners.id", ondelete="CASCADE"), primary_key=True),
    Column("capability_id", ForeignKey("partner_types.id", ondelete="RESTRICT"), primary_key=True),
)


class PartnerType(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "partner_types"

    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")


class PartnerTier(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "partner_tiers"

    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    rank: Mapped[int] = mapped_column(unique=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")


class Country(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "countries"

    code: Mapped[str] = mapped_column(String(2), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")


class Partner(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "partners"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING_APPROVAL', 'ACTIVE', 'REJECTED', 'SUSPENDED', 'INACTIVE')",
            name="valid_status",
        ),
    )

    organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True, unique=True
    )
    capabilities: Mapped[list[PartnerType]] = relationship(
        secondary=partner_capabilities, lazy="selectin"
    )

    code: Mapped[str | None] = mapped_column(String(30), unique=True, index=True, nullable=True)
    company_name: Mapped[str] = mapped_column(String(200), index=True)
    legal_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    company_email: Mapped[str] = mapped_column(String(320), index=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_contact_name: Mapped[str] = mapped_column(String(200))
    primary_contact_email: Mapped[str] = mapped_column(String(320))
    primary_contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), default=PartnerStatus.PENDING_APPROVAL, index=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    partner_type_id: Mapped[UUID] = mapped_column(
        ForeignKey("partner_types.id", ondelete="RESTRICT"), index=True
    )
    tier_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("partner_tiers.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    created_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    partner_type: Mapped[PartnerType] = relationship(lazy="joined")
    tier: Mapped[PartnerTier | None] = relationship(lazy="joined")
    countries: Mapped[list[Country]] = relationship(secondary=partner_countries, lazy="selectin")
    users: Mapped[list[User]] = relationship(
        back_populates="partner", foreign_keys="User.partner_id", lazy="selectin"
    )
    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_id])
    approved_by: Mapped[User | None] = relationship(foreign_keys=[approved_by_id])
