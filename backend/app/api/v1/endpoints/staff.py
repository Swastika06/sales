from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.api.v1.endpoints.auth import user_response
from app.db.session import get_db
from app.models.identity import Role, User
from app.models.onboarding import OnboardingMail
from app.schemas.staff import STAFF_ROLES, StaffUserCreate, StaffUserRead
from app.services.onboarding import limit, require_admin
from app.services.staff import create_staff_user, queue_staff_invitation

router = APIRouter()


async def response(session: AsyncSession, target: User) -> StaffUserRead:
    status = await session.scalar(
        select(OnboardingMail.status)
        .where(OnboardingMail.user_id == target.id)
        .order_by(OnboardingMail.created_at.desc(), OnboardingMail.id.desc())
        .limit(1)
    )
    return StaffUserRead(
        **user_response(target).model_dump(), created_at=target.created_at, mail_status=status
    )


@router.get("/roles")
async def roles(user: User = Depends(get_current_user)) -> list[dict[str, str]]:
    require_admin(user)
    return [{"code": code, "name": name} for code, name in STAFF_ROLES.items()]


@router.get("", response_model=list[StaffUserRead])
async def users(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)
) -> list[StaffUserRead]:
    require_admin(user)
    targets = await session.scalars(
        select(User)
        .where(User.partner_id.is_(None), User.roles.any(Role.code.in_(STAFF_ROLES)))
        .order_by(User.created_at.desc())
        .limit(200)
    )
    return [await response(session, target) for target in targets]


@router.post("", response_model=StaffUserRead, status_code=201)
async def create(
    body: StaffUserCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> StaffUserRead:
    target = await create_staff_user(session, body, user)
    await session.commit()
    return await response(session, target)


@router.post("/{user_id}/invitation", response_model=StaffUserRead)
async def reissue_invitation(
    user_id: UUID,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> StaffUserRead:
    require_admin(user)
    await limit(session, "staff-invitation", str(user_id), 5, 3600)
    target = await session.scalar(
        select(User)
        .where(User.id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if target is None or target.partner_id is not None:
        raise HTTPException(404, "Staff user not found")
    codes = [role.code for role in target.roles if role.code in STAFF_ROLES]
    if not codes:
        raise HTTPException(404, "Staff user not found")
    if not target.is_active or not target.must_change_password:
        raise HTTPException(409, "An invitation can only be sent before the first password change")
    await queue_staff_invitation(session, target, codes[0])
    from app.services.audit import record_audit_event

    await record_audit_event(
        session,
        action="STAFF_INVITATION_REISSUED",
        entity_type="user",
        entity_id=str(target.id),
        actor_user_id=user.id,
        request_id=request.state.request_id,
    )
    await session.commit()
    return await response(session, target)
