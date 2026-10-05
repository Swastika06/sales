from collections.abc import Callable, Coroutine
from typing import Any
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.identity import Role, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/token")


async def get_current_user(
    request: Request, token: str = Depends(oauth2_scheme), session: AsyncSession = Depends(get_db)
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id = UUID(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
        raise credentials_error from exc

    result = await session.execute(
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.roles).selectinload(Role.permissions))
    )
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise credentials_error
    restricted = payload.get("password_change_required", False)
    if restricted and not user.must_change_password:
        raise credentials_error
    if user.must_change_password and not restricted:
        raise credentials_error
    if user.must_change_password and request.url.path not in {
        settings.API_V1_PREFIX + "/auth/me",
        settings.API_V1_PREFIX + "/auth/change-password",
    }:
        raise HTTPException(403, "Change your temporary password before accessing the portal")
    if user.partner_id:
        from app.models.partner import Partner, PartnerStatus
        from app.services.onboarding import activation_guard

        partner = await session.get(Partner, user.partner_id)
        if partner is None or partner.status != PartnerStatus.ACTIVE:
            raise credentials_error
        await activation_guard(session, user.partner_id)
    return user


def require_permissions(
    *required: str,
) -> Callable[..., Coroutine[Any, Any, User]]:
    async def permission_dependency(user: User = Depends(get_current_user)) -> User:
        if user.is_superuser:
            return user
        granted = {permission.code for role in user.roles for permission in role.permissions}
        if not set(required).issubset(granted):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return permission_dependency
