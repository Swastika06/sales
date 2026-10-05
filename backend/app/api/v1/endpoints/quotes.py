from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_current_user
from app.api.v1.endpoints.workflow_common import (
    actor_role,
    make_reference,
    require_sales_manage,
    require_tcg,
)
from app.db.session import get_db
from app.domain.access import is_tcg_user
from app.domain.workflows import QUOTE_TRANSITIONS, WorkflowError, ensure_transition
from app.models.commercial import CommercialContract, CommercialSnapshot
from app.models.identity import User
from app.models.partner import Partner
from app.models.pricing import Sku
from app.models.sales import (
    DealApprovalStatus,
    Quote,
    QuoteItem,
    QuoteRevision,
    QuoteStatus,
)
from app.schemas.sales import QuoteCreate, QuoteItemCreate, QuoteRead, StatusChange
from app.services.audit import record_audit_event
from app.services.commercial import (
    freeze_commercial,
    lock_opportunity,
    resolve_unit_price,
    tcg_organization,
)
from app.services.commercial_access import (
    require_execution_access,
    require_opportunity_access,
    visible_contract_ids,
)

router = APIRouter()


def quote_response(quote: Quote, user: User) -> QuoteRead:
    result = QuoteRead.model_validate(quote)
    if not is_tcg_user(user):
        for item in result.items:
            item.pricing_snapshot = {
                key: value
                for key, value in item.pricing_snapshot.items()
                if key in {"as_of", "resolved_unit_price", "engagement_model"}
            }
    return result


async def authorize_quote(
    session: AsyncSession,
    user: User,
    quote: Quote,
    *,
    accepting: bool = False,
) -> None:
    deal = await require_opportunity_access(session, user, quote.opportunity_id, commercial=True)
    contract = (
        await session.get(CommercialContract, quote.contract_id) if quote.contract_id else None
    )
    if quote.commercial_model != deal.engagement_model:
        raise HTTPException(409, "Create a replacement quote for the changed engagement model")
    if contract is None:
        raise HTTPException(409, "Legacy quote requires a reviewed replacement contract")
    await require_execution_access(
        session,
        user,
        deal,
        accepting=accepting,
        buyer_id=contract.buyer_organization_id,
        seller_id=contract.seller_organization_id,
    )


CENT = Decimal("0.01")


async def get_quote(session: AsyncSession, quote_id: UUID) -> Quote:
    quote = await session.scalar(
        select(Quote)
        .where(Quote.id == quote_id)
        .with_for_update(of=Quote)
        .options(selectinload(Quote.items), selectinload(Quote.revisions))
    )
    if quote is None:
        raise HTTPException(status_code=404, detail="Quote not found")
    return quote


def recalculate(quote: Quote) -> None:
    subtotal = sum((item.unit_price * item.quantity for item in quote.items), Decimal("0"))
    total = sum((item.line_total for item in quote.items), Decimal("0"))
    quote.subtotal = subtotal.quantize(CENT, rounding=ROUND_HALF_UP)
    quote.total = total.quantize(CENT, rounding=ROUND_HALF_UP)
    quote.discount_total = (quote.subtotal - quote.total).quantize(CENT, rounding=ROUND_HALF_UP)


def snapshot(quote: Quote) -> dict[str, object]:
    return {
        "reference": quote.reference,
        "currency": quote.currency,
        "commercial_model": quote.commercial_model,
        "valid_until": quote.valid_until.isoformat() if quote.valid_until else None,
        "subtotal": str(quote.subtotal),
        "discount_total": str(quote.discount_total),
        "total": str(quote.total),
        "items": [
            {
                "sku_id": str(item.sku_id),
                "sku_code": item.sku_code,
                "sku_name": item.sku_name,
                "quantity": str(item.quantity),
                "unit_price": str(item.unit_price),
                "discount_percentage": str(item.discount_percentage),
                "line_total": str(item.line_total),
                "pricing_snapshot": item.pricing_snapshot,
            }
            for item in quote.items
        ],
    }


@router.get("", response_model=list[QuoteRead])
async def list_quotes(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[QuoteRead]:
    statement = select(Quote).options(selectinload(Quote.items)).order_by(Quote.created_at.desc())
    if not is_tcg_user(user):
        statement = statement.where(Quote.contract_id.in_(visible_contract_ids(user)))
    return [quote_response(item, user) for item in await session.scalars(statement)]


@router.post("", response_model=QuoteRead, status_code=201)
async def create_quote(
    body: QuoteCreate,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> QuoteRead:
    require_sales_manage(user)
    deal = await lock_opportunity(session, body.opportunity_id)
    if deal is None:
        raise HTTPException(status_code=404, detail="Deal not found")
    await require_opportunity_access(session, user, deal.id, commercial=True)
    if body.commercial_model is not None and body.commercial_model != deal.engagement_model:
        raise HTTPException(422, "The quote inherits the opportunity engagement model")
    contract = await session.get(CommercialContract, body.contract_id) if body.contract_id else None
    if contract and contract.opportunity_id != deal.id:
        raise HTTPException(422, "Contract belongs to another opportunity")
    if body.contract_id and contract is None:
        raise HTTPException(404, "Contract not found")
    if contract is None:
        if deal.engagement_model == "SYSTEM_INTEGRATOR":
            raise HTTPException(422, "Select the agreed SI contracting parties first")
        tcg = await tcg_organization(session)
        partner = await session.get(Partner, deal.partner_id) if deal.partner_id else None
        buyer = (
            partner.organization_id
            if deal.engagement_model == "RESELLER" and partner
            else deal.customer.organization_id
        )
        if buyer is None:
            raise HTTPException(422, "Configure the customer organization first")
        contract = CommercialContract(
            opportunity_id=deal.id,
            seller_organization_id=tcg.id,
            buyer_organization_id=buyer,
            kind="WHOLESALE" if deal.engagement_model == "RESELLER" else "CUSTOMER",
        )
        session.add(contract)
        await session.flush()
    tcg = await tcg_organization(session)
    if contract.seller_organization_id != tcg.id:
        raise HTTPException(422, "TCG quotes must use the TCG selling contract")
    if contract.status != "DRAFT":
        raise HTTPException(409, "Use a draft contract for a new quote")
    await require_execution_access(
        session,
        user,
        deal,
        buyer_id=contract.buyer_organization_id,
        seller_id=contract.seller_organization_id,
    )
    if deal.approval_status != DealApprovalStatus.APPROVED:
        raise HTTPException(status_code=409, detail="Quotes require an approved deal")
    quote = Quote(
        reference=make_reference("QTE"),
        opportunity_id=deal.id,
        partner_id=deal.partner_id,
        commercial_model=deal.engagement_model,
        contract_id=contract.id,
        valid_until=body.valid_until,
        notes=body.notes,
        created_by_id=user.id,
    )
    session.add(quote)
    await session.flush()
    await record_audit_event(
        session,
        action="quote.created",
        entity_type="quote",
        entity_id=str(quote.id),
        actor_user_id=user.id,
        actor_role=actor_role(user),
        request_id=getattr(request.state, "request_id", None),
    )
    await session.commit()
    return quote_response(await get_quote(session, quote.id), user)


@router.post("/{quote_id}/items", response_model=QuoteRead)
async def add_quote_item(
    quote_id: UUID,
    body: QuoteItemCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> QuoteRead:
    quote = await get_quote(session, quote_id)
    await authorize_quote(session, user, quote)
    require_sales_manage(user)
    if quote.status != QuoteStatus.DRAFT:
        raise HTTPException(status_code=409, detail="Only draft quotes can be edited")
    if body.discount_percentage != 0:
        raise HTTPException(
            422, "Configure discounts in approved terms; line discounts do not stack"
        )
    deal = await lock_opportunity(session, quote.opportunity_id)
    sku = await session.get(Sku, body.sku_id)
    if sku is None:
        raise HTTPException(422, "Unknown SKU")
    from app.models.commercial import SolutionComponent

    if not await session.scalar(
        select(SolutionComponent.id)
        .where(
            SolutionComponent.opportunity_id == deal.id,
            SolutionComponent.product_id == sku.product_id,
        )
        .limit(1)
    ):
        raise HTTPException(422, "The SKU must belong to an opportunity solution component")
    amount, resolved = await resolve_unit_price(
        session, quote.commercial_model, body.sku_id, deal=deal, contract_id=quote.contract_id
    )
    item = QuoteItem(
        quote_id=quote.id,
        sku_id=sku.id,
        sku_code=sku.code,
        sku_name=sku.name,
        quantity=body.quantity,
        unit_price=amount,
        discount_percentage=Decimal("0"),
        line_total=(amount * body.quantity).quantize(CENT, rounding=ROUND_HALF_UP),
        pricing_snapshot=resolved,
    )
    quote.items.append(item)
    recalculate(quote)
    await session.commit()
    return quote_response(await get_quote(session, quote.id), user)


@router.post("/{quote_id}/status", response_model=QuoteRead)
async def change_quote_status(
    quote_id: UUID,
    body: StatusChange,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> QuoteRead:
    quote = await get_quote(session, quote_id)
    await authorize_quote(session, user, quote)
    require_sales_manage(user)
    if body.status == QuoteStatus.FINAL:
        require_tcg(user)
        if not quote.items:
            raise HTTPException(status_code=409, detail="A quote needs at least one item")
    if body.status == QuoteStatus.ACCEPTED:
        await authorize_quote(session, user, quote, accepting=True)
        frozen = await session.scalar(
            select(CommercialSnapshot).where(
                CommercialSnapshot.quote_id == quote.id,
                CommercialSnapshot.revision == quote.current_revision,
            )
        )
        deal = await lock_opportunity(session, quote.opportunity_id)
        if frozen is None or frozen.engagement_version != deal.commercial_version:
            raise HTTPException(
                409, "Commercial details changed; revise and finalize this quote again"
            )
        if deal.approval_status != "APPROVED":
            raise HTTPException(409, "The opportunity requires commercial reapproval")
        contract = await session.get(CommercialContract, quote.contract_id)
        if contract is None or contract.status != "DRAFT":
            raise HTTPException(409, "The contracting agreement already has an accepted quote")
        if contract is not None:
            contract.status = "ACCEPTED"
            contract.accepted_quote_id = quote.id
    try:
        ensure_transition(quote.status, body.status, QUOTE_TRANSITIONS)
    except WorkflowError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    old_status = quote.status
    quote.status = body.status
    if body.status == QuoteStatus.FINAL:
        recalculate(quote)
        deal = await lock_opportunity(session, quote.opportunity_id)
        if deal.approval_status != "APPROVED":
            raise HTTPException(409, "The opportunity requires commercial reapproval")
        quote.current_revision += 1
        frozen = await freeze_commercial(session, deal, quote)
        session.add(
            QuoteRevision(
                quote_id=quote.id,
                revision_number=quote.current_revision,
                snapshot=snapshot(quote) | {"commercial_snapshot_id": str(frozen.id)},
                created_by_id=user.id,
            )
        )
    await record_audit_event(
        session,
        action="quote.status_changed",
        entity_type="quote",
        entity_id=str(quote.id),
        actor_user_id=user.id,
        actor_role=actor_role(user),
        old_values={"status": old_status},
        new_values={"status": body.status},
        request_id=getattr(request.state, "request_id", None),
    )
    await session.commit()
    return quote_response(await get_quote(session, quote.id), user)


@router.post("/{quote_id}/revise", response_model=QuoteRead)
async def revise_quote(
    quote_id: UUID,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> QuoteRead:
    require_tcg(user)
    require_sales_manage(user)
    quote = await get_quote(session, quote_id)
    if quote.status != QuoteStatus.FINAL:
        raise HTTPException(status_code=409, detail="Only a final quote can be revised")
    quote.status = QuoteStatus.DRAFT
    await record_audit_event(
        session,
        action="quote.revision_started",
        entity_type="quote",
        entity_id=str(quote.id),
        actor_user_id=user.id,
        actor_role=actor_role(user),
        old_values={"status": QuoteStatus.FINAL, "revision": quote.current_revision},
        new_values={"status": QuoteStatus.DRAFT},
        request_id=getattr(request.state, "request_id", None),
    )
    await session.commit()
    return quote_response(await get_quote(session, quote.id), user)


@router.delete("/{quote_id}/items/{item_id}", response_model=QuoteRead)
async def remove_quote_item(
    quote_id: UUID,
    item_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> QuoteRead:
    quote = await get_quote(session, quote_id)
    await authorize_quote(session, user, quote)
    require_sales_manage(user)
    if quote.status != QuoteStatus.DRAFT:
        raise HTTPException(status_code=409, detail="Only draft quotes can be edited")
    item = next((candidate for candidate in quote.items if candidate.id == item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Quote item not found")
    await session.delete(item)
    quote.items.remove(item)
    recalculate(quote)
    await session.commit()
    return quote_response(await get_quote(session, quote.id), user)
