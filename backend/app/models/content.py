from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DocumentCategory(StrEnum):
    SALES_ENABLEMENT = "SALES_ENABLEMENT"
    PRODUCT_DOCUMENTATION = "PRODUCT_DOCUMENTATION"
    IMPLEMENTATION_GUIDE = "IMPLEMENTATION_GUIDE"
    PRICING = "PRICING"
    PROPOSAL_TEMPLATE = "PROPOSAL_TEMPLATE"
    SOW_TEMPLATE = "SOW_TEMPLATE"
    RFP = "RFP"
    OTHER = "OTHER"


class DocumentVisibility(StrEnum):
    ALL_PARTNERS = "ALL_PARTNERS"
    PARTNER_TYPE = "PARTNER_TYPE"
    SPECIFIC_PARTNER = "SPECIFIC_PARTNER"
    TCG_INTERNAL = "TCG_INTERNAL"


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "category IN ('SALES_ENABLEMENT', 'PRODUCT_DOCUMENTATION', "
            "'IMPLEMENTATION_GUIDE', 'PRICING', 'PROPOSAL_TEMPLATE', "
            "'SOW_TEMPLATE', 'RFP', 'OTHER')",
            name="valid_category",
        ),
        CheckConstraint(
            "visibility IN ('ALL_PARTNERS', 'PARTNER_TYPE', 'PARTNER_TIER', "
            "'SPECIFIC_PARTNER', 'TCG_INTERNAL')",
            name="valid_visibility",
        ),
    )

    title: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    visibility: Mapped[str] = mapped_column(String(40), index=True)
    product_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True
    )
    partner_type_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("partner_types.id", ondelete="CASCADE"), nullable=True
    )
    partner_tier_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("partner_tiers.id", ondelete="CASCADE"), nullable=True
    )
    partner_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("partners.id", ondelete="CASCADE"), nullable=True, index=True
    )
    created_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true", index=True)

    versions: Mapped[list[DocumentVersion]] = relationship(
        back_populates="document", cascade="all, delete-orphan", lazy="selectin"
    )


class DocumentVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_document_version"),
        CheckConstraint("version_number > 0", name="positive_version"),
        CheckConstraint("size_bytes >= 0", name="non_negative_size"),
    )

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    version_number: Mapped[int] = mapped_column(Integer)
    object_key: Mapped[str] = mapped_column(String(700), unique=True)
    file_name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(150))
    size_bytes: Mapped[int] = mapped_column()
    checksum_sha256: Mapped[str] = mapped_column(String(64))
    change_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    uploaded_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))

    document: Mapped[Document] = relationship(back_populates="versions")
