from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_current_user
from app.api.v1.endpoints.quotes import authorize_quote
from app.api.v1.endpoints.workflow_common import (
    actor_role,
    make_reference,
    require_partner_scope,
    require_sales_manage,
    require_tcg,
    store_attachment,
)
from app.db.session import get_db
from app.domain.access import is_tcg_user
from app.domain.workflows import (
    MAF_TRANSITIONS,
    ORDER_TRANSITIONS,
    WorkflowError,
    ensure_transition,
)
from app.models.identity import User
from app.models.partner import Partner, PartnerStatus
from app.models.sales import (
    DealApprovalStatus,
    DomainEvent,
    MafRequest,
    MafStatus,
    Opportunity,
    Order,
    OrderStatus,
    OrderStatusHistory,
    Quote,
    QuoteRevision,
    QuoteStatus,
    StoredAttachment,
)
from app.schemas.content import DownloadRead
from app.schemas.sales import (
    AttachmentRead,
    MafCreate,
    MafRead,
    OrderCreate,
    OrderRead,
    StatusChange,
)
from app.services.audit import record_audit_event
from app.services.commercial_access import (
    require_opportunity_access,
    visible_contract_ids,
    visible_opportunity_ids,
)
from app.storage.client import presigned_download_url

maf_router = APIRouter()
orders_router = APIRouter()


async def authorize_order(session: AsyncSession, user: User, order: Order) -> None:
    quote = await session.get(Quote, order.quote_id)
    if quote is None:
        raise HTTPException(404, "Quote not found")
    await authorize_quote(session, user, quote)


async def get_maf(session: AsyncSession, maf_id: UUID) -> MafRequest:
    maf = await session.get(MafRequest, maf_id)
    if maf is None:
        raise HTTPException(status_code=404, detail="MAF request not found")
    return maf


async def get_order(session: AsyncSession, order_id: UUID) -> Order:
    order = await session.scalar(
        select(Order)
        .where(Order.id == order_id)
        .with_for_update(of=Order)
        .options(selectinload(Order.status_history))
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@maf_router.get("", response_model=list[MafRead])
async def list_mafs(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[MafRead]:
    statement = select(MafRequest).order_by(MafRequest.created_at.desc())
    if not is_tcg_user(user):
        statement = statement.where(
            MafRequest.partner_id == user.partner_id,
            MafRequest.opportunity_id.in_(visible_opportunity_ids(user)),
        )
    return [MafRead.model_validate(item) for item in await session.scalars(statement)]


@maf_router.post("", response_model=MafRead, status_code=201)
async def create_maf(
    body: MafCreate,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> MafRead:
    require_sales_manage(user)
    deal = await session.get(Opportunity, body.opportunity_id)
    if deal is None:
        raise HTTPException(status_code=404, detail="Deal not found")
    await require_opportunity_access(session, user, deal.id)
    target_partner = body.partner_id or deal.partner_id
    if target_partner is None:
        raise HTTPException(422, "MAF authorization requires an actual participating partner")
    require_partner_scope(user, target_partner)
    partner = await session.get(Partner, target_partner)
    if partner is None or partner.status != PartnerStatus.ACTIVE:
        raise HTTPException(422, "MAF requires an active partner")
    from app.models.commercial import OpportunityParticipant

    if not await session.scalar(
        select(OpportunityParticipant.id).where(
            OpportunityParticipant.opportunity_id == deal.id,
            OpportunityParticipant.organization_id == partner.organization_id,
            OpportunityParticipant.active.is_(True),
        )
    ):
        raise HTTPException(422, "The MAF partner must participate in this opportunity")
    if deal.approval_status != DealApprovalStatus.APPROVED:
        raise HTTPException(status_code=409, detail="MAF requests require an approved deal")
    maf = MafRequest(
        reference=make_reference("MAF"),
        opportunity_id=deal.id,
        partner_id=target_partner,
        tender_reference=body.tender_reference,
        tender_authority=body.tender_authority,
        tender_due_date=body.tender_due_date,
        tender_value=body.tender_value,
        details=body.details,
        created_by_id=user.id,
    )
    session.add(maf)
    await session.flush()
    await record_audit_event(
        session,
        action="maf.created",
        entity_type="maf_request",
        entity_id=str(maf.id),
        actor_user_id=user.id,
        actor_role=actor_role(user),
        request_id=getattr(request.state, "request_id", None),
    )
    await session.commit()
    await session.refresh(maf)
    return MafRead.model_validate(maf)


@maf_router.post("/{maf_id}/status", response_model=MafRead)
async def change_maf_status(
    maf_id: UUID,
    body: StatusChange,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> MafRead:
    maf = await get_maf(session, maf_id)
    require_partner_scope(user, maf.partner_id)
    await require_opportunity_access(session, user, maf.opportunity_id)
    require_sales_manage(user)
    admin_statuses = {
        MafStatus.UNDER_REVIEW,
        MafStatus.RETURNED_FOR_CORRECTION,
        MafStatus.APPROVED,
        MafStatus.REJECTED,
        MafStatus.ISSUED,
        MafStatus.EXPIRED,
    }
    if body.status in admin_statuses:
        require_tcg(user)
    if body.status in {MafStatus.RETURNED_FOR_CORRECTION, MafStatus.REJECTED} and not body.reason:
        raise HTTPException(status_code=422, detail="A reason is required")
    if body.status == MafStatus.ISSUED:
        issued_document = await session.scalar(
            select(StoredAttachment.id)
            .where(
                StoredAttachment.owner_type == "MAF",
                StoredAttachment.owner_id == maf.id,
                StoredAttachment.kind == "ISSUED_DOCUMENT",
            )
            .limit(1)
        )
        if issued_document is None:
            raise HTTPException(status_code=409, detail="Upload the issued MAF document first")
    try:
        ensure_transition(maf.status, body.status, MAF_TRANSITIONS)
    except WorkflowError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    previous = maf.status
    maf.status = body.status
    maf.review_reason = body.reason
    if body.status in admin_statuses:
        maf.reviewed_by_id = user.id
    if body.status == MafStatus.ISSUED:
        maf.expires_at = datetime.now(UTC) + timedelta(days=90)
    await record_audit_event(
        session,
        action="maf.status_changed",
        entity_type="maf_request",
        entity_id=str(maf.id),
        actor_user_id=user.id,
        actor_role=actor_role(user),
        old_values={"status": previous},
        new_values={"status": body.status, "reason": body.reason},
        request_id=getattr(request.state, "request_id", None),
    )
    await session.commit()
    await session.refresh(maf)
    return MafRead.model_validate(maf)


@maf_router.post("/{maf_id}/attachments", response_model=AttachmentRead, status_code=201)
async def upload_maf_attachment(
    maf_id: UUID,
    kind: str = "SUPPORTING",
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> AttachmentRead:
    maf = await get_maf(session, maf_id)
    require_partner_scope(user, maf.partner_id)
    await require_opportunity_access(session, user, maf.opportunity_id)
    require_sales_manage(user)
    if kind == "ISSUED_DOCUMENT":
        require_tcg(user)
    attachment = await store_attachment(
        session, owner_type="MAF", owner_id=maf.id, kind=kind, file=file, user=user
    )
    await session.commit()
    await session.refresh(attachment)
    return AttachmentRead.model_validate(attachment)


@maf_router.get("/{maf_id}/attachments", response_model=list[AttachmentRead])
async def list_maf_attachments(
    maf_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[AttachmentRead]:
    maf = await get_maf(session, maf_id)
    require_partner_scope(user, maf.partner_id)
    await require_opportunity_access(session, user, maf.opportunity_id)
    rows = await session.scalars(
        select(StoredAttachment).where(
            StoredAttachment.owner_type == "MAF", StoredAttachment.owner_id == maf.id
        )
    )
    return [AttachmentRead.model_validate(row) for row in rows]


@maf_router.get("/{maf_id}/attachments/{attachment_id}/download", response_model=DownloadRead)
async def download_maf_attachment(
    maf_id: UUID,
    attachment_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> DownloadRead:
    maf = await get_maf(session, maf_id)
    require_partner_scope(user, maf.partner_id)
    await require_opportunity_access(session, user, maf.opportunity_id)
    attachment = await session.get(StoredAttachment, attachment_id)
    if attachment is None or attachment.owner_type != "MAF" or attachment.owner_id != maf.id:
        raise HTTPException(status_code=404, detail="Attachment not found")
    return DownloadRead(url=presigned_download_url(attachment.object_key, attachment.file_name))


@orders_router.get("", response_model=list[OrderRead])
async def list_orders(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[OrderRead]:
    statement = (
        select(Order).options(selectinload(Order.status_history)).order_by(Order.created_at.desc())
    )
    if not is_tcg_user(user):
        statement = statement.join(Quote, Quote.id == Order.quote_id).where(
            Quote.contract_id.in_(visible_contract_ids(user))
        )
    return [OrderRead.model_validate(item) for item in await session.scalars(statement)]


@orders_router.post("", response_model=OrderRead, status_code=201)
async def create_order(
    body: OrderCreate,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> OrderRead:
    require_sales_manage(user)
    quote = await session.scalar(
        select(Quote).where(Quote.id == body.quote_id).options(selectinload(Quote.items))
    )
    if quote is None:
        raise HTTPException(status_code=404, detail="Quote not found")
    await authorize_quote(session, user, quote)
    if quote.status != QuoteStatus.ACCEPTED:
        raise HTTPException(status_code=409, detail="Orders require an accepted quote")
    if await session.scalar(select(Order.id).where(Order.quote_id == quote.id)) is not None:
        raise HTTPException(status_code=409, detail="An order already exists for this quote")
    revision = await session.scalar(
        select(QuoteRevision).where(
            QuoteRevision.quote_id == quote.id,
            QuoteRevision.revision_number == quote.current_revision,
        )
    )
    if revision is None:
        raise HTTPException(409, "Accepted quote revision is missing")
    order = Order(
        reference=make_reference("ORD"),
        quote_id=quote.id,
        partner_id=quote.partner_id,
        billing_name=body.billing_name,
        billing_address=body.billing_address,
        billing_email=body.billing_email,
        total=quote.total,
        quote_snapshot=revision.snapshot,
        created_by_id=user.id,
    )
    session.add(order)
    await session.flush()
    session.add(
        OrderStatusHistory(
            order_id=order.id,
            from_status=None,
            to_status=OrderStatus.DRAFT,
            note="Order created from accepted quote",
            changed_by_id=user.id,
        )
    )
    await record_audit_event(
        session,
        action="order.created",
        entity_type="order",
        entity_id=str(order.id),
        actor_user_id=user.id,
        actor_role=actor_role(user),
        request_id=getattr(request.state, "request_id", None),
    )
    await session.commit()
    return OrderRead.model_validate(await get_order(session, order.id))


@orders_router.post("/{order_id}/status", response_model=OrderRead)
async def change_order_status(
    order_id: UUID,
    body: StatusChange,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> OrderRead:
    order = await get_order(session, order_id)
    await authorize_order(session, user, order)
    require_sales_manage(user)
    admin_statuses = {
        OrderStatus.UNDER_REVIEW,
        OrderStatus.RETURNED_FOR_CORRECTION,
        OrderStatus.CONFIRMED,
        OrderStatus.PROVISIONING,
        OrderStatus.ACTIVE,
    }
    if body.status in admin_statuses:
        require_tcg(user)
    if body.status == OrderStatus.RETURNED_FOR_CORRECTION and not body.reason:
        raise HTTPException(status_code=422, detail="A return reason is required")
    if body.status == OrderStatus.SUBMITTED:
        purchase_order = await session.scalar(
            select(StoredAttachment.id)
            .where(
                StoredAttachment.owner_type == "ORDER",
                StoredAttachment.owner_id == order.id,
                StoredAttachment.kind == "PURCHASE_ORDER",
            )
            .limit(1)
        )
        if purchase_order is None:
            raise HTTPException(
                status_code=409, detail="A purchase order or signed contract is required"
            )
    try:
        ensure_transition(order.status, body.status, ORDER_TRANSITIONS)
    except WorkflowError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    previous = order.status
    order.status = body.status
    order.review_reason = body.reason
    if body.status in admin_statuses:
        order.reviewed_by_id = user.id
    session.add(
        OrderStatusHistory(
            order_id=order.id,
            from_status=previous,
            to_status=body.status,
            note=body.reason,
            changed_by_id=user.id,
        )
    )
    if body.status == OrderStatus.CONFIRMED:
        order.confirmed_at = datetime.now(UTC)
        session.add(
            DomainEvent(
                event_type="ORDER_CONFIRMED",
                aggregate_type="order",
                aggregate_id=order.id,
                payload={
                    "order_id": str(order.id),
                    "order_reference": order.reference,
                    "quote_id": str(order.quote_id),
                    "partner_id": str(order.partner_id) if order.partner_id else None,
                    "total": str(order.total),
                    "currency": order.currency,
                },
            )
        )
    await record_audit_event(
        session,
        action="order.status_changed",
        entity_type="order",
        entity_id=str(order.id),
        actor_user_id=user.id,
        actor_role=actor_role(user),
        old_values={"status": previous},
        new_values={"status": body.status, "reason": body.reason},
        request_id=getattr(request.state, "request_id", None),
    )
    await session.commit()
    return OrderRead.model_validate(await get_order(session, order.id))


@orders_router.post("/{order_id}/attachments", response_model=AttachmentRead, status_code=201)
async def upload_order_attachment(
    order_id: UUID,
    kind: str = "PURCHASE_ORDER",
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> AttachmentRead:
    order = await get_order(session, order_id)
    await authorize_order(session, user, order)
    require_sales_manage(user)
    attachment = await store_attachment(
        session, owner_type="ORDER", owner_id=order.id, kind=kind, file=file, user=user
    )
    await session.commit()
    await session.refresh(attachment)
    return AttachmentRead.model_validate(attachment)


@orders_router.get("/{order_id}/attachments", response_model=list[AttachmentRead])
async def list_order_attachments(
    order_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[AttachmentRead]:
    order = await get_order(session, order_id)
    await authorize_order(session, user, order)
    rows = await session.scalars(
        select(StoredAttachment).where(
            StoredAttachment.owner_type == "ORDER", StoredAttachment.owner_id == order.id
        )
    )
    return [AttachmentRead.model_validate(row) for row in rows]


@orders_router.get("/{order_id}/attachments/{attachment_id}/download", response_model=DownloadRead)
async def download_order_attachment(
    order_id: UUID,
    attachment_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> DownloadRead:
    order = await get_order(session, order_id)
    await authorize_order(session, user, order)
    attachment = await session.get(StoredAttachment, attachment_id)
    if attachment is None or attachment.owner_type != "ORDER" or attachment.owner_id != order.id:
        raise HTTPException(status_code=404, detail="Attachment not found")
    return DownloadRead(url=presigned_download_url(attachment.object_key, attachment.file_name))
