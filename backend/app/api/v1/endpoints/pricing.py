from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.domain.access import is_tcg_admin, is_tcg_user
from app.models.identity import User
from app.schemas.commercial import EngagementModel
from app.schemas.pricing import PartnerPricingResponse
from app.services.pricing import resolve_partner_pricing

router = APIRouter()


@router.get("/resolved", response_model=PartnerPricingResponse)
async def resolved_pricing(
    engagement_model: EngagementModel,
    partner_id: UUID | None = None,
    as_of: date | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> PartnerPricingResponse:
    if not is_tcg_user(user):
        if user.partner_id is None or partner_id not in {None, user.partner_id}:
            raise HTTPException(403, "Pricing is restricted to your own organization")
        if engagement_model in {"DIRECT", "REFERRAL"}:
            raise HTTPException(403, "Customer pricing is managed by TCG for this model")
        partner_id = user.partner_id
    return await resolve_partner_pricing(
        session,
        partner_id,
        engagement_model=engagement_model,
        as_of=as_of,
        include_breakdown=is_tcg_admin(user),
    )
