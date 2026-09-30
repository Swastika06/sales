from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_current_user
from app.api.v1.endpoints.workflow_common import (
    actor_role,
    make_reference,
    require_sales_manage,
    require_tcg,
    store_attachment,
)
from app.db.session import get_db
from app.domain.access import is_tcg_user
from app.domain.workflows import (
    DEAL_TRANSITIONS,
    WorkflowError,
    ensure_transition,
    validate_pipeline_change,
)
from app.models.identity import User
from app.models.pricing import Product
from app.models.sales import (
    Customer,
    DealApprovalStatus,
    Opportunity,
    OpportunityStageHistory,
    PipelineStage,
    StoredAttachment,
)
from app.schemas.sales import (
    AttachmentRead,
    CustomerCreate,
    CustomerRead,
    DealCreate,
    DealRead,
    DealStageChange,
    ReasonBody,
)
from app.services.audit import record_audit_event
from app.services.commercial import (
    accrue_conversion,
    initialize_engagement,
    validate_engagement,
)
from app.services.commercial_access import require_opportunity_access, visible_opportunity_ids
from app.storage.client import presigned_download_url

router = APIRouter()


def deal_response(deal: Opportunity, user: User) -> DealRead:
    result = DealRead.model_validate(deal)
    if not is_tcg_user(user):
        result.actual_contract_value = None
        result.stage_history = [
            history.model_copy(update={"note": None}) for history in result.stage_history
        ]
    return result


async def get_deal(session: AsyncSession, deal_id: UUID) -> Opportunity:
    deal = await session.scalar(
        select(Opportunity)
        .where(Opportunity.id == deal_id)
        .with_for_update(of=Opportunity)
        .options(selectinload(Opportunity.customer), selectinload(Opportunity.stage_history))
    )
    if deal is None:
        raise HTTPException(status_code=404, detail="Deal not found")
    return deal


async def ensure_no_protected_conflict(session: AsyncSession, deal: Opportunity) -> None:
    lock_key = f"deal-protection:{deal.customer_id}:{deal.product_id}"
    from app.services.commercial import advisory_scope_lock

    await advisory_scope_lock(session, lock_key)
    conflict = await session.scalar(
        select(Opportunity.id)
        .where(
            Opportunity.id != deal.id,
            Opportunity.customer_id == deal.customer_id,
            Opportunity.product_id == deal.product_id,
            Opportunity.approval_status == DealApprovalStatus.APPROVED,
            Opportunity.protection_expires_at > datetime.now(UTC),
            Opportunity.stage.notin_([PipelineStage.WON, PipelineStage.LOST]),
        )
        .limit(1)
    )
    if conflict is not None:
        raise HTTPException(
            status_code=409,
            detail="An active protected deal already exists for this customer and product",
        )


async def validate_customer_organization(
    session: AsyncSession,
    user: User,
    organization_id: UUID | None,
) -> None:
    if organization_id is None:
        return
    require_tcg(user)
    from app.models.commercial import Organization

    org = await session.get(Organization, organization_id)
    if org is None or not org.is_active:
        raise HTTPException(422, "Select an existing active customer organization")


@router.get("/customers", response_model=list[CustomerRead])
async def list_customers(
    search: str | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[CustomerRead]:
    statement = select(Customer).order_by(Customer.name)
    if not is_tcg_user(user):
        statement = (
            statement.join(Opportunity, Opportunity.customer_id == Customer.id)
            .where(Opportunity.id.in_(visible_opportunity_ids(user)))
            .distinct()
        )
    if search:
        statement = statement.where(Customer.name.ilike(f"%{search.strip()}%"))
    return [CustomerRead.model_validate(item) for item in await session.scalars(statement)]


@router.post("/customers", response_model=CustomerRead, status_code=201)
async def create_customer(
    body: CustomerCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CustomerRead:
    require_sales_manage(user)
    await validate_customer_organization(session, user, body.organization_id)
    values = body.model_dump()
    values["country_code"] = body.country_code.upper()
    customer = Customer(**values, created_by_id=user.id)
    session.add(customer)
    await session.commit()
    await session.refresh(customer)
    return CustomerRead.model_validate(customer)


@router.get("", response_model=list[DealRead])
async def list_deals(
    status: str | None = None,
    stage: str | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[DealRead]:
    statement = (
        select(Opportunity)
        .options(selectinload(Opportunity.customer), selectinload(Opportunity.stage_history))
        .order_by(Opportunity.created_at.desc())
    )
    if not is_tcg_user(user):
        statement = statement.where(Opportunity.id.in_(visible_opportunity_ids(user)))
    if status:
        statement = statement.where(Opportunity.approval_status == status)
    if stage:
        statement = statement.where(Opportunity.stage == stage)
    return [deal_response(item, user) for item in await session.scalars(statement)]


@router.post("", response_model=DealRead, status_code=201)
async def create_deal(
    body: DealCreate,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> DealRead:
    require_sales_manage(user)
    partner_id: UUID | None
    customer: Customer | None
    if not is_tcg_user(user):
        if body.engagement_model == "DIRECT":
            raise HTTPException(403, "Only TCG can create Direct opportunities")
        if user.partner_id is None or body.partner_id not in {None, user.partner_id}:
            raise HTTPException(403, "Submit opportunities for your own organization")
        partner_id = user.partner_id
    else:
        partner_id = body.partner_id
    from app.services.commercial import partner_for_model

    await partner_for_model(session, partner_id, body.engagement_model)
    if await session.get(Product, body.product_id) is None:
        raise HTTPException(status_code=404, detail="Product not found")
    if body.customer_id is None and body.customer is None:
        raise HTTPException(status_code=422, detail="customer_id or customer is required")
    if body.customer_id is not None and body.customer is not None:
        raise HTTPException(status_code=422, detail="Provide customer_id or customer, not both")
    customer_id = body.customer_id
    if body.customer:
        await validate_customer_organization(session, user, body.customer.organization_id)
        customer_values = body.customer.model_dump()
        customer_values["country_code"] = body.customer.country_code.upper()
        customer = Customer(**customer_values, created_by_id=user.id)
        session.add(customer)
        await session.flush()
        customer_id = customer.id
    elif await session.get(Customer, customer_id) is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    if not is_tcg_user(user) and body.customer_id:
        customer = await session.get(Customer, body.customer_id)
        shared = await session.scalar(
            select(Opportunity.id)
            .where(
                Opportunity.customer_id == body.customer_id,
                Opportunity.id.in_(visible_opportunity_ids(user)),
            )
            .limit(1)
        )
        if customer is None or (customer.created_by_id != user.id and not shared):
            raise HTTPException(404, "Customer not found")
    deal = Opportunity(
        engagement_model=body.engagement_model,
        reference=make_reference("DEAL"),
        partner_id=partner_id,
        customer_id=customer_id,
        product_id=body.product_id,
        name=body.name,
        description=body.description,
        estimated_value=body.estimated_value,
        expected_close_date=body.expected_close_date,
        created_by_id=user.id,
    )
    session.add(deal)
    await session.flush()
    deal = await get_deal(session, deal.id)
    await initialize_engagement(session, deal, body.engagement_model, user)
    session.add(
        OpportunityStageHistory(
            opportunity_id=deal.id,
            from_stage=None,
            to_stage=PipelineStage.REGISTERED,
            note="Deal registered",
            changed_by_id=user.id,
        )
    )
    await record_audit_event(
        session,
        action="deal.created",
        entity_type="opportunity",
        entity_id=str(deal.id),
        actor_user_id=user.id,
        actor_role=actor_role(user),
        request_id=getattr(request.state, "request_id", None),
    )
    await session.commit()
    return deal_response(await get_deal(session, deal.id), user)


@router.get("/{deal_id}", response_model=DealRead)
async def read_deal(
    deal_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> DealRead:
    deal = await get_deal(session, deal_id)
    await require_opportunity_access(session, user, deal.id)
    return deal_response(deal, user)


@router.post("/{deal_id}/submit", response_model=DealRead)
async def submit_deal(
    deal_id: UUID,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> DealRead:
    deal = await get_deal(session, deal_id)
    await require_opportunity_access(session, user, deal.id)
    require_sales_manage(user)
    try:
        ensure_transition(deal.approval_status, DealApprovalStatus.SUBMITTED, DEAL_TRANSITIONS)
    except WorkflowError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await ensure_no_protected_conflict(session, deal)
    deal.approval_status = DealApprovalStatus.SUBMITTED
    deal.submitted_at = datetime.now(UTC)
    deal.review_reason = None
    await record_audit_event(
        session,
        action="deal.submitted",
        entity_type="opportunity",
        entity_id=str(deal.id),
        actor_user_id=user.id,
        actor_role=actor_role(user),
        request_id=getattr(request.state, "request_id", None),
    )
    await session.commit()
    return deal_response(await get_deal(session, deal.id), user)


@router.post("/{deal_id}/approve", response_model=DealRead)
async def approve_deal(
    deal_id: UUID,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> DealRead:
    require_tcg(user)
    deal = await get_deal(session, deal_id)
    try:
        ensure_transition(deal.approval_status, DealApprovalStatus.APPROVED, DEAL_TRANSITIONS)
    except WorkflowError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    require_sales_manage(user)
    await validate_engagement(session, deal)
    await ensure_no_protected_conflict(session, deal)
    now = datetime.now(UTC)
    deal.approval_status = DealApprovalStatus.APPROVED
    deal.approved_at = now
    deal.protection_expires_at = now + timedelta(days=90)
    deal.reviewed_by_id = user.id
    deal.responsible_user_id = deal.responsible_user_id or user.id
    deal.review_reason = None
    await record_audit_event(
        session,
        action="deal.approved",
        entity_type="opportunity",
        entity_id=str(deal.id),
        actor_user_id=user.id,
        actor_role=actor_role(user),
        new_values={"protection_expires_at": deal.protection_expires_at.isoformat()},
        request_id=getattr(request.state, "request_id", None),
    )
    await session.commit()
    return deal_response(await get_deal(session, deal.id), user)


@router.post("/{deal_id}/reject", response_model=DealRead)
async def reject_deal(
    deal_id: UUID,
    body: ReasonBody,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> DealRead:
    require_tcg(user)
    deal = await get_deal(session, deal_id)
    try:
        ensure_transition(deal.approval_status, DealApprovalStatus.REJECTED, DEAL_TRANSITIONS)
    except WorkflowError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    deal.approval_status = DealApprovalStatus.REJECTED
    deal.review_reason = body.reason
    deal.reviewed_by_id = user.id
    await record_audit_event(
        session,
        action="deal.rejected",
        entity_type="opportunity",
        entity_id=str(deal.id),
        actor_user_id=user.id,
        actor_role=actor_role(user),
        new_values={"reason": body.reason},
        request_id=getattr(request.state, "request_id", None),
    )
    await session.commit()
    return deal_response(await get_deal(session, deal.id), user)


@router.post("/{deal_id}/stage", response_model=DealRead)
async def change_stage(
    deal_id: UUID,
    body: DealStageChange,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> DealRead:
    deal = await get_deal(session, deal_id)
    await require_opportunity_access(session, user, deal.id)
    require_sales_manage(user)
    if deal.approval_status != DealApprovalStatus.APPROVED:
        raise HTTPException(
            status_code=409, detail="Only approved deals can move through the pipeline"
        )
    if deal.stage in {PipelineStage.WON, PipelineStage.LOST}:
        raise HTTPException(status_code=409, detail="Won and lost deals are terminal")
    try:
        validate_pipeline_change(
            body.stage,
            actual_contract_value=body.actual_contract_value,
            actual_close_date=body.actual_close_date,
            lost_reason=body.lost_reason,
        )
    except WorkflowError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if deal.engagement_model in {"DIRECT", "REFERRAL"}:
        require_tcg(user)
    previous = deal.stage
    deal.stage = body.stage
    if body.stage == PipelineStage.WON:
        deal.actual_contract_value = body.actual_contract_value
        deal.actual_close_date = body.actual_close_date
    if body.stage == PipelineStage.LOST:
        deal.lost_reason = body.lost_reason
    if body.stage == PipelineStage.WON:
        await accrue_conversion(session, deal)
    session.add(
        OpportunityStageHistory(
            opportunity_id=deal.id,
            from_stage=previous,
            to_stage=body.stage,
            note=body.note or body.lost_reason,
            changed_by_id=user.id,
        )
    )
    await record_audit_event(
        session,
        action="deal.stage_changed",
        entity_type="opportunity",
        entity_id=str(deal.id),
        actor_user_id=user.id,
        actor_role=actor_role(user),
        old_values={"stage": previous},
        new_values={"stage": body.stage},
        request_id=getattr(request.state, "request_id", None),
    )
    await session.commit()
    return deal_response(await get_deal(session, deal.id), user)


@router.post("/{deal_id}/attachments", response_model=AttachmentRead, status_code=201)
async def upload_deal_attachment(
    deal_id: UUID,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> AttachmentRead:
    deal = await get_deal(session, deal_id)
    await require_opportunity_access(session, user, deal.id, commercial=True)
    require_sales_manage(user)
    attachment = await store_attachment(
        session, owner_type="DEAL", owner_id=deal.id, kind="SUPPORTING", file=file, user=user
    )
    await session.commit()
    await session.refresh(attachment)
    return AttachmentRead.model_validate(attachment)


@router.get("/{deal_id}/attachments", response_model=list[AttachmentRead])
async def list_deal_attachments(
    deal_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[AttachmentRead]:
    deal = await get_deal(session, deal_id)
    await require_opportunity_access(session, user, deal.id, commercial=True)
    rows = await session.scalars(
        select(StoredAttachment).where(
            StoredAttachment.owner_type == "DEAL", StoredAttachment.owner_id == deal.id
        )
    )
    return [AttachmentRead.model_validate(row) for row in rows]


@router.get("/{deal_id}/attachments/{attachment_id}/download")
async def download_deal_attachment(
    deal_id: UUID,
    attachment_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str | int]:
    deal = await get_deal(session, deal_id)
    await require_opportunity_access(session, user, deal.id, commercial=True)
    attachment = await session.get(StoredAttachment, attachment_id)
    if attachment is None or attachment.owner_type != "DEAL" or attachment.owner_id != deal.id:
        raise HTTPException(status_code=404, detail="Attachment not found")
    return {
        "url": presigned_download_url(attachment.object_key, attachment.file_name),
        "expires_in_seconds": 600,
    }
