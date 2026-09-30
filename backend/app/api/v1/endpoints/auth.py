from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.db.session import get_db
from app.models.identity import Role, User
from app.schemas.auth import TokenResponse, UserRead
from app.services.audit import record_audit_event

router = APIRouter()


def user_response(user: User) -> UserRead:
    return UserRead(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        partner_id=user.partner_id,
        roles=sorted(role.code for role in user.roles),
        permissions=sorted(
            {permission.code for role in user.roles for permission in role.permissions}
        ),
    )


@router.post("/token", response_model=TokenResponse)
async def issue_token(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    result = await session.execute(
        select(User)
        .where(User.email == form.username.lower())
        .options(selectinload(User.roles).selectinload(Role.permissions))
    )
    user = result.scalar_one_or_none()
    if (
        user is None
        or not user.is_active
        or not verify_password(form.password, user.hashed_password)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.partner_id:
        from app.models.partner import Partner, PartnerStatus
        from app.services.onboarding import activation_guard
        partner = await session.get(Partner, user.partner_id)
        if partner is None or partner.status != PartnerStatus.ACTIVE:
            raise HTTPException(401, "Your account is not active")
        await activation_guard(session, user.partner_id)

    await record_audit_event(
        session,
        action="USER_LOGIN",
        entity_type="user",
        entity_id=str(user.id),
        actor_user_id=user.id,
        actor_role=user.roles[0].code if user.roles else None,
        request_id=request.state.request_id,
    )
    await session.commit()
    return TokenResponse(
        access_token=create_access_token(
            str(user.id), extra_claims={"roles": [role.code for role in user.roles]}
        ),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserRead)
async def me(user: User = Depends(get_current_user)) -> UserRead:
    return user_response(user)
