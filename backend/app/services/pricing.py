from datetime import date
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.pricing import Product, Sku
from app.schemas.pricing import PartnerPricingResponse, PriceBreakdown, ResolvedPriceRead
from app.services.commercial import resolve_unit_price
from app.services.partners import load_partner


async def resolve_partner_pricing(
    session: AsyncSession,
    partner_id: UUID | None,
    *,
    engagement_model: str,
    as_of: date | None = None,
    include_breakdown: bool = False,
) -> PartnerPricingResponse:
    today = as_of or date.today()
    partner = await load_partner(session, partner_id) if partner_id else None
    if engagement_model != "DIRECT" and partner is None:
        raise HTTPException(422, "Select a partner for this engagement model")
    if (
        partner
        and engagement_model != "DIRECT"
        and engagement_model not in {c.code for c in partner.capabilities}
    ):
        raise HTTPException(422, "Partner does not have this capability")
    items = []
    for sku in await session.scalars(
        select(Sku)
        .options(joinedload(Sku.product))
        .join(Product)
        .where(Sku.is_active.is_(True), Product.is_active.is_(True))
    ):
        try:
            amount, snapshot = await resolve_unit_price(
                session, engagement_model, sku.id, partner_id=partner_id, as_of=today
            )
        except HTTPException as exc:
            if exc.status_code == 422 and "No applicable catalog" in str(exc.detail):
                continue
            raise
        items.append(
            ResolvedPriceRead(
                product_id=sku.product.id,
                product_code=sku.product.code,
                product_name=sku.product.name,
                sku_id=sku.id,
                sku_code=sku.code,
                sku_name=sku.name,
                sku_description=sku.description,
                unit=sku.unit,
                final_price=amount,
                effective_from=today,
                commercial_model=engagement_model,
                breakdown=PriceBreakdown(sources=snapshot["sources"])
                if include_breakdown
                else None,
            )
        )
    return PartnerPricingResponse(
        partner_id=partner_id,
        partner_name=partner.company_name if partner else "TCG Direct",
        as_of=today,
        items=items,
    )
