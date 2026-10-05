import json
import secrets

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.models.identity import Role, User
from app.models.onboarding import OnboardingMail
from app.schemas.staff import STAFF_ROLES, StaffUserCreate
from app.services.audit import record_audit_event
from app.services.onboarding import mail_cipher, now, require_admin


async def create_staff_user(session: AsyncSession, body: StaffUserCreate, actor: User) -> User:
    require_admin(actor)
    email = str(body.email).lower()
    if await session.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists")
    role = await session.scalar(select(Role).where(Role.code == body.role_code))
    if role is None:
        raise HTTPException(503, "Apply migrations and seed the internal roles first")
    password = secrets.token_urlsafe(24)
    target = User(
        email=email,
        full_name=body.full_name,
        hashed_password=hash_password(password),
        is_active=True,
        is_superuser=False,
        must_change_password=True,
        roles=[role],
    )
    session.add(target)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, "An account with this email already exists") from exc
    await queue_staff_invitation(session, target, body.role_code)
    await record_audit_event(
        session,
        action="STAFF_USER_CREATED",
        entity_type="user",
        entity_id=str(target.id),
        actor_user_id=actor.id,
        new_values={"role_code": body.role_code},
    )
    return target


async def queue_staff_invitation(session: AsyncSession, target: User, role_code: str) -> None:
    password = secrets.token_urlsafe(16)
    target.hashed_password = hash_password(password)
    payload = {
        "to": target.email,
        "subject": "Your TCG staff account",
        "credential_hash": target.hashed_password,
        "body": "An administrator has created your "
        + STAFF_ROLES[role_code]
        + " account.\n\nEmail: "
        + target.email
        + "\nTemporary login password: "
        + password
        + "\nSign in: "
        + settings.PUBLIC_PORTAL_URL.rstrip("/")
        + "/login"
        + "\nYou must change this password on your first login before accessing the workspace.",
    }
    session.add(
        OnboardingMail(
            user_id=target.id,
            kind="STAFF_PASSWORD",
            available_at=now(),
            created_at=now(),
            encrypted_payload=mail_cipher().encrypt(json.dumps(payload).encode()).decode(),
        )
    )
