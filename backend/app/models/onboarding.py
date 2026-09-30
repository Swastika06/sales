"""Private partner onboarding; deliberately separate from the document library."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class OnboardingApplication(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "onboarding_applications"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','PENDING_ADMIN_REVIEW','LEGAL_REVIEW','CHANGES_REQUESTED',"
            "'REJECTED','PENDING_EMAIL_VERIFICATION','COMPLETED')",
            name="valid_status",
        ),
    )
    partner_id: Mapped[UUID] = mapped_column(ForeignKey("partners.id"), unique=True)
    applicant_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(40), default="DRAFT", index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    reviewed_revision: Mapped[int | None] = mapped_column(Integer)
    token_version: Mapped[int] = mapped_column(Integer, default=1)
    assigned_to_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    review_comment: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    otp_hash: Mapped[str | None] = mapped_column(String(64))
    otp_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    otp_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    otp_attempts: Mapped[int] = mapped_column(Integer, default=0)


class OnboardingDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "onboarding_documents"
    application_id: Mapped[UUID] = mapped_column(
        ForeignKey("onboarding_applications.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(30))
    number: Mapped[str] = mapped_column(String(100))
    revision: Mapped[int] = mapped_column(Integer)
    filename: Mapped[str] = mapped_column(String(200))
    object_key: Mapped[str] = mapped_column(String(500), unique=True)
    content_type: Mapped[str] = mapped_column(String(100))
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    scan_status: Mapped[str] = mapped_column(String(30))


class OnboardingMail(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "onboarding_mail"
    application_id: Mapped[UUID] = mapped_column(
        ForeignKey("onboarding_applications.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(30))
    encrypted_payload: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(100))


class OnboardingRateLimit(Base):
    __tablename__ = "onboarding_rate_limits"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
