import base64
import hashlib
import hmac
import json
import re
import secrets
import socket
import struct
from datetime import UTC, datetime, timedelta
from pathlib import PurePath
from typing import Any
from uuid import UUID

import jwt
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.domain.access import is_tcg_admin, role_codes
from app.models.identity import User
from app.models.onboarding import (
    OnboardingApplication,
    OnboardingDocument,
    OnboardingMail,
    OnboardingRateLimit,
)
from app.models.partner import Partner
from app.services.audit import record_audit_event

DOCUMENT_REQUIREMENTS = {
    "COMPANY_LICENSE": {"label": "Company license", "pattern": r"^.{2,100}$"},
    "PAN": {"label": "PAN", "pattern": r"^[A-Z]{5}[0-9]{4}[A-Z]$"},
    "GSTIN": {"label": "GSTIN", "pattern": r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$"},
}
EDITABLE = {"DRAFT", "CHANGES_REQUESTED"}


def now() -> datetime:
    return datetime.now(UTC)


def aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def needs_documents(codes: list[str]) -> bool:
    return bool({"RESELLER", "REFERRAL"} & set(codes))


def digest(value: str) -> str:
    return hmac.new(settings.JWT_SECRET_KEY.encode(), value.encode(), hashlib.sha256).hexdigest()


def mail_cipher() -> Fernet:
    key = hashlib.sha256(("onboarding-mail:" + settings.JWT_SECRET_KEY).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def application_token(application: OnboardingApplication) -> str:
    return jwt.encode(
        {
            "sub": str(application.id),
            "aud": "onboarding",
            "v": application.token_version,
            "exp": now() + timedelta(days=7),
        },
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


async def token_application(
    session: AsyncSession, token: str, *, lock: bool = False
) -> OnboardingApplication:
    try:
        claims = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            audience="onboarding",
        )
        application_id = UUID(claims["sub"])
    except (jwt.InvalidTokenError, ValueError, KeyError) as exc:
        raise HTTPException(401, "Application session expired. Sign in to resume.") from exc
    query = select(OnboardingApplication).where(OnboardingApplication.id == application_id)
    application = await session.scalar(
        query.with_for_update().execution_options(populate_existing=True) if lock else query
    )
    if application is None or claims.get("v") != application.token_version:
        raise HTTPException(401, "Application session expired. Sign in to resume.")
    return application


async def audit(
    session: AsyncSession,
    application: OnboardingApplication,
    action: str,
    actor: User | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    await record_audit_event(
        session,
        action="ONBOARDING_" + action,
        entity_type="onboarding",
        entity_id=str(application.id),
        actor_user_id=actor.id if actor else None,
        new_values={
            "status": application.status,
            "revision": application.revision,
            **(detail or {}),
        },
    )


async def limit(
    session: AsyncSession, scope: str, identity: str, maximum: int, seconds: int
) -> None:
    """Persist attempts before business logic; one database counter across API workers."""
    key = digest(scope + ":" + identity)
    row = await session.scalar(
        select(OnboardingRateLimit).where(OnboardingRateLimit.key == key).with_for_update()
    )
    if row is None:
        try:
            async with session.begin_nested():
                row = OnboardingRateLimit(
                    key=key, count=0, expires_at=now() + timedelta(seconds=seconds)
                )
                session.add(row)
                await session.flush()
        except IntegrityError:
            row = await session.scalar(
                select(OnboardingRateLimit).where(OnboardingRateLimit.key == key).with_for_update()
            )
    if aware(row.expires_at) <= now():
        row.count = 0
        row.expires_at = now() + timedelta(seconds=seconds)
    if row.count >= maximum:
        await session.commit()
        raise HTTPException(
            429,
            "Too many attempts. Please try again later.",
            headers={
                "Retry-After": str(max(1, int((aware(row.expires_at) - now()).total_seconds())))
            },
        )
    row.count += 1
    await session.commit()


async def create_application(
    session: AsyncSession, partner: Partner, applicant: User
) -> OnboardingApplication:
    await session.flush()
    application = OnboardingApplication(partner_id=partner.id, applicant_id=applicant.id)
    session.add(application)
    await session.flush()
    await audit(session, application, "DRAFT_CREATED")
    return application


async def latest_documents(
    session: AsyncSession, application_id: UUID
) -> list[OnboardingDocument]:
    rows = list(
        await session.scalars(
            select(OnboardingDocument)
            .where(OnboardingDocument.application_id == application_id)
            .order_by(OnboardingDocument.revision.desc(), OnboardingDocument.created_at.desc())
        )
    )
    latest: dict[str, OnboardingDocument] = {}
    for row in rows:
        latest.setdefault(row.kind, row)
    return list(latest.values())


async def validate_submission(
    session: AsyncSession, application: OnboardingApplication
) -> None:
    partner = await session.get(Partner, application.partner_id)
    if partner is None:
        raise HTTPException(409, "The application partner no longer exists")
    docs = {doc.kind: doc for doc in await latest_documents(session, application.id)}
    if needs_documents([c.code for c in partner.capabilities]):
        missing = set(DOCUMENT_REQUIREMENTS) - docs.keys()
        if missing:
            raise HTTPException(422, "Upload all required documents: " + ", ".join(sorted(missing)))
        if docs["GSTIN"].number[2:12] != docs["PAN"].number:
            raise HTTPException(422, "The PAN within the GSTIN must match the supplied PAN.")
    if settings.APP_ENV == "production" and any(d.scan_status != "CLEAN" for d in docs.values()):
        raise HTTPException(409, "Documents must pass malware scanning before review.")


def require_admin(user: User) -> None:
    if not is_tcg_admin(user):
        raise HTTPException(403, "TCG Admin access is required")


def require_reviewer(user: User, application: OnboardingApplication) -> None:
    if "TCG_LEGAL" not in role_codes(user) or application.assigned_to_id != user.id:
        raise HTTPException(403, "Only the assigned legal reviewer can decide this application")


def require_staff_view(user: User, application: OnboardingApplication) -> None:
    if not is_tcg_admin(user) and not (
        "TCG_LEGAL" in role_codes(user) and application.assigned_to_id == user.id
    ):
        raise HTTPException(403, "You cannot access this application")


def validate_file(filename: str, data: bytes) -> str:
    extension = PurePath(filename).suffix.lower()
    if data.startswith(b"%PDF-") and b"%%EOF" in data[-2048:] and extension == ".pdf":
        return "application/pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n") and extension == ".png":
        return "image/png"
    if (
        data.startswith(b"\xff\xd8\xff")
        and data.endswith(b"\xff\xd9")
        and extension in {".jpg", ".jpeg"}
    ):
        return "image/jpeg"
    raise HTTPException(422, "Upload a valid PDF, PNG, or JPEG with the matching file extension.")


def scan_file(data: bytes) -> str:
    if not settings.CLAMAV_HOST:
        if settings.APP_ENV == "production":
            raise HTTPException(503, "Document scanning is not configured")
        return "NOT_CONFIGURED"
    try:
        with socket.create_connection(
            (settings.CLAMAV_HOST, settings.CLAMAV_PORT), timeout=30
        ) as client:
            client.sendall(b"zINSTREAM\0")
            for offset in range(0, len(data), 65536):
                chunk = data[offset : offset + 65536]
                client.sendall(struct.pack("!I", len(chunk)) + chunk)
            client.sendall(struct.pack("!I", 0))
            response = bytearray()
            while len(response) < 4096:
                chunk = client.recv(1024)
                if not chunk:
                    break
                response.extend(chunk)
                if b"\0" in chunk:
                    break
        if b"FOUND" in response:
            raise HTTPException(422, "The uploaded file did not pass the security scan.")
        if not response.rstrip(b"\0\n").endswith(b": OK"):
            raise OSError("Unexpected scanner response")
        return "CLEAN"
    except OSError as exc:
        raise HTTPException(
            503, "Document scanning is temporarily unavailable. Try again."
        ) from exc


async def queue_mail(
    session: AsyncSession,
    application: OnboardingApplication,
    kind: str,
    message: str,
    *,
    code: str | None = None,
) -> None:
    applicant = await session.get(User, application.applicant_id)
    if applicant is None:
        raise HTTPException(409, "The application user no longer exists")
    link = (
        settings.PUBLIC_PORTAL_URL.rstrip("/")
        + "/onboarding#token="
        + application_token(application)
    )
    payload: dict[str, Any] = {
        "to": applicant.email,
        "subject": "TCG partner application",
        "body": message + "\n\nContinue your application: " + link,
    }
    if code:
        payload["otp_hash"] = application.otp_hash
    mail = OnboardingMail(
        application_id=application.id,
        kind=kind,
        encrypted_payload=mail_cipher().encrypt(json.dumps(payload).encode()).decode(),
        available_at=now(),
    )
    session.add(mail)


async def queue_otp(session: AsyncSession, application: OnboardingApplication) -> None:
    code = f"{secrets.randbelow(1000000):06d}"
    application.otp_hash = digest(str(application.id) + ":" + code)
    application.otp_expires_at = now() + timedelta(minutes=10)
    application.otp_sent_at = now()
    application.otp_attempts = 0
    await queue_mail(
        session,
        application,
        "OTP",
        "Legal has approved your application. Your activation code is "
        + code
        + ". It expires in 10 minutes. Request another code on the activation page if needed.",
        code=code,
    )


async def activation_guard(session: AsyncSession, partner_id: UUID) -> None:
    application = await session.scalar(
        select(OnboardingApplication).where(OnboardingApplication.partner_id == partner_id)
    )
    if application and application.status != "COMPLETED":
        raise HTTPException(
            409, "Complete document review and email verification before activation."
        )


def validate_number(kind: str, number: str) -> str:
    if kind not in DOCUMENT_REQUIREMENTS:
        raise HTTPException(422, "Unknown document type")
    number = number.strip().upper()
    if not re.fullmatch(DOCUMENT_REQUIREMENTS[kind]["pattern"], number):
        raise HTTPException(
            422, "Enter a valid " + DOCUMENT_REQUIREMENTS[kind]["label"] + " number."
        )
    return number
