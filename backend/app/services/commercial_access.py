"""Opportunity membership and explicit commercial sharing."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import Select, false, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.access import is_tcg_user
from app.models.commercial import CommercialContract, OpportunityParticipant
from app.models.identity import User
from app.models.partner import Partner, PartnerStatus, PartnerType
from app.models.sales import Opportunity


def visible_opportunity_ids(user: User, *, commercial: bool = False) -> Select[tuple[UUID]]:
    statement = (
        select(OpportunityParticipant.opportunity_id)
        .join(Partner, Partner.organization_id == OpportunityParticipant.organization_id)
        .where(
            Partner.id == user.partner_id,
            Partner.status == PartnerStatus.ACTIVE,
            Partner.capabilities.any(PartnerType.code == OpportunityParticipant.capability),
            OpportunityParticipant.active.is_(True),
            OpportunityParticipant.access_level.in_(["PROGRESS", "COMMERCIAL"]),
        )
    )
    if user.partner_id is None:
        statement = statement.where(false())
    if commercial:
        statement = statement.where(
            OpportunityParticipant.access_level == "COMMERCIAL",
            OpportunityParticipant.capability.in_(["RESELLER", "SYSTEM_INTEGRATOR"]),
        )
    return statement


async def require_opportunity_access(
    session: AsyncSession,
    user: User,
    opportunity_id: UUID,
    *,
    commercial: bool = False,
) -> Opportunity:
    deal = await session.get(Opportunity, opportunity_id)
    if deal is None:
        raise HTTPException(404, "Opportunity not found")
    if is_tcg_user(user):
        return deal
    visible = await session.scalar(
        visible_opportunity_ids(user, commercial=commercial).where(
            OpportunityParticipant.opportunity_id == opportunity_id
        )
    )
    if visible is None:
        raise HTTPException(404, "Opportunity not found")
    return deal


async def user_organization(session: AsyncSession, user: User) -> UUID | None:
    if user.partner_id is None:
        return None
    return await session.scalar(
        select(Partner.organization_id).where(
            Partner.id == user.partner_id, Partner.status == PartnerStatus.ACTIVE
        )
    )


async def require_execution_access(
    session: AsyncSession,
    user: User,
    deal: Opportunity,
    *,
    accepting: bool = False,
    buyer_id: UUID | None = None,
    seller_id: UUID | None = None,
) -> None:
    await require_opportunity_access(session, user, deal.id, commercial=True)
    if deal.migration_review_required or deal.engagement_model is None:
        raise HTTPException(409, "Classify this legacy opportunity before commercial actions")
    if deal.engagement_model in {"DIRECT", "REFERRAL"}:
        if not is_tcg_user(user):
            raise HTTPException(403, "TCG executes customer quotes and orders for this engagement")
        return
    organization_id = await user_organization(session, user)
    if accepting:
        if deal.engagement_model == "RESELLER":
            if is_tcg_user(user) or organization_id != buyer_id:
                raise HTTPException(403, "The contracting reseller accepts this wholesale quote")
        elif is_tcg_user(user):
            # TCG records acceptance on behalf of an external customer only.
            partner_buyer = await session.scalar(
                select(Partner.id).where(Partner.organization_id == buyer_id)
            )
            if partner_buyer:
                raise HTTPException(403, "The contracting partner must accept this quote")
        elif organization_id != buyer_id:
            raise HTTPException(403, "Only the contracting buyer can accept this quote")
    elif not is_tcg_user(user) and organization_id not in {buyer_id, seller_id}:
        raise HTTPException(403, "This action belongs to the specified contracting parties")


def visible_contract_ids(user: User) -> Select[tuple[UUID]]:
    own_org = select(Partner.organization_id).where(
        Partner.id == user.partner_id, Partner.status == PartnerStatus.ACTIVE
    )
    return (
        select(CommercialContract.id)
        .join(Opportunity)
        .where(
            Opportunity.engagement_model.in_(["RESELLER", "SYSTEM_INTEGRATOR"]),
            CommercialContract.opportunity_id.in_(visible_opportunity_ids(user, commercial=True)),
            or_(
                CommercialContract.buyer_organization_id.in_(own_org),
                CommercialContract.seller_organization_id.in_(own_org),
            ),
        )
    )
