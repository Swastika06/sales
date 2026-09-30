from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.api.v1.endpoints.workflow_common import require_sales_manage, require_tcg
from app.db.session import get_db
from app.domain.access import is_tcg_admin, is_tcg_user
from app.domain.commercial import calculate_commercial, validate_parameters
from app.models.commercial import (
    CommercialContract,
    CommercialSnapshot,
    CommercialTermVersion,
    CommissionAccrual,
    CommissionAdjustment,
    CommissionPayment,
    ConversionEvidence,
    OpportunityParticipant,
    OpportunityRole,
    OpportunityVendorLink,
    Organization,
    PartnerAgreement,
    SolutionComponent,
    VendorAgreement,
    VendorProfile,
)
from app.models.identity import User
from app.models.sales import Opportunity, Quote
from app.schemas.commercial import (
    AccrualAdjustmentCreate,
    CalculationRequest,
    CalculationResult,
    ContractCreate,
    ConversionCreate,
    EngagementUpdate,
    OrganizationCreate,
    PartnerAgreementCreate,
    SettlementCreate,
    TermCreate,
    VendorAgreementCreate,
    VendorLinkCreate,
    VendorProfileCreate,
)
from app.services.audit import record_audit_event
from app.services.commercial import (
    accrue_conversion,
    advisory_scope_lock,
    apply_engagement,
    lock_opportunity,
    partner_for_model,
    preview_commercial,
    row_json,
    tcg_organization,
)
from app.services.commercial_access import (
    require_opportunity_access,
    user_organization,
    visible_opportunity_ids,
)

router = APIRouter()


class VersionBody(BaseModel):
    expected_version: int = Field(ge=0)


def admin(user: User) -> None:
    if not is_tcg_admin(user):
        raise HTTPException(403, "TCG administrator access is required")


async def audit(session: AsyncSession, user: User, action: str, row: Any) -> None:
    await record_audit_event(
        session,
        action=action,
        entity_type=row.__tablename__,
        entity_id=str(row.id),
        actor_user_id=user.id,
    )


@router.post("/calculate", response_model=CalculationResult)
async def calculate(
    body: CalculationRequest,
    user: User = Depends(get_current_user),
) -> CalculationResult:
    require_tcg(user)
    try:
        return calculate_commercial(body)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/organizations")
async def organizations(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    require_tcg(user)
    return [
        row_json(row)
        for row in await session.scalars(select(Organization).order_by(Organization.legal_name))
    ]


@router.post("/organizations", status_code=201)
async def create_organization(
    body: OrganizationCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    admin(user)
    await advisory_scope_lock(session, f"organization:{body.identifier.strip().lower()}")
    existing = await session.scalar(
        select(Organization).where(Organization.identifier == body.identifier.strip().lower())
    )
    if existing:
        raise HTTPException(409, "Use the existing organization with this identifier")
    row = Organization(
        legal_name=body.legal_name.strip(), identifier=body.identifier.strip().lower()
    )
    session.add(row)
    await session.flush()
    await audit(session, user, "organization.created", row)
    await session.commit()
    await session.refresh(row)
    return row_json(row)


@router.post("/vendors", status_code=201)
async def create_vendor(
    body: VendorProfileCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    admin(user)
    if not await session.get(Organization, body.organization_id):
        raise HTTPException(422, "Select an existing organization")
    if await session.scalar(
        select(VendorProfile.id).where(VendorProfile.organization_id == body.organization_id)
    ):
        raise HTTPException(409, "This organization already has a vendor profile")
    row = VendorProfile(**body.model_dump())
    session.add(row)
    await session.flush()
    await audit(session, user, "vendor.created", row)
    await session.commit()
    await session.refresh(row)
    return row_json(row)


@router.get("/agreements")
async def agreements(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    admin(user)
    return {
        "partners": [row_json(row) for row in await session.scalars(select(PartnerAgreement))],
        "vendors": [row_json(row) for row in await session.scalars(select(VendorAgreement))],
        "vendor_profiles": [row_json(row) for row in await session.scalars(select(VendorProfile))],
    }


@router.post("/partner-agreements", status_code=201)
async def create_partner_agreement(
    body: PartnerAgreementCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    admin(user)
    if body.engagement_model == "DIRECT":
        raise HTTPException(422, "Direct is not a partner capability")
    await partner_for_model(session, body.partner_id, body.engagement_model)
    if body.effective_until and body.effective_until < body.effective_from:
        raise HTTPException(422, "Invalid agreement dates")
    row = PartnerAgreement(**body.model_dump())
    session.add(row)
    await session.flush()
    await audit(session, user, "partner_agreement.created", row)
    await session.commit()
    await session.refresh(row)
    return row_json(row)


@router.post("/vendor-agreements", status_code=201)
async def create_vendor_agreement(
    body: VendorAgreementCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    admin(user)
    if not await session.scalar(
        select(VendorProfile.id).where(
            VendorProfile.organization_id == body.provider_organization_id
        )
    ):
        raise HTTPException(422, "Create the provider's vendor profile first")
    if not await session.get(Organization, body.buyer_organization_id):
        raise HTTPException(422, "Unknown contracting buyer")
    if body.provider_organization_id == body.buyer_organization_id:
        raise HTTPException(422, "Provider and buyer must be distinct")
    if body.effective_until and body.effective_until < body.effective_from:
        raise HTTPException(422, "Invalid agreement dates")
    row = VendorAgreement(**body.model_dump())
    session.add(row)
    await session.flush()
    await audit(session, user, "vendor_agreement.created", row)
    await session.commit()
    await session.refresh(row)
    return row_json(row)


@router.get("/migration-review")
async def migration_review(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    require_tcg(user)
    return [
        row_json(row)
        for row in await session.scalars(
            select(Opportunity).where(Opportunity.migration_review_required.is_(True))
        )
    ]


@router.get("/opportunities/{opportunity_id}")
async def engagement(
    opportunity_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    deal = await require_opportunity_access(session, user, opportunity_id)
    organization = await user_organization(session, user)
    result: dict[str, Any] = {
        "opportunity_id": str(deal.id),
        "engagement_model": deal.engagement_model,
        "commercial_version": deal.commercial_version,
        "migration_review_required": deal.migration_review_required,
    }
    if not is_tcg_user(user):
        result["participant"] = [
            row_json(p)
            for p in await session.scalars(
                select(OpportunityParticipant).where(
                    OpportunityParticipant.opportunity_id == deal.id,
                    OpportunityParticipant.organization_id == organization,
                )
            )
        ]
        return result
    for key, model in (
        ("participants", OpportunityParticipant),
        ("roles", OpportunityRole),
        ("components", SolutionComponent),
        ("vendor_links", OpportunityVendorLink),
        ("contracts", CommercialContract),
    ):
        result[key] = [
            row_json(row)
            for row in await session.scalars(select(model).where(model.opportunity_id == deal.id))
        ]
    return result


@router.put("/opportunities/{opportunity_id}")
async def configure_engagement(
    opportunity_id: UUID,
    body: EngagementUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_tcg(user)
    require_sales_manage(user)
    deal = await lock_opportunity(session, opportunity_id, body.expected_version)
    await apply_engagement(session, deal, body)
    await audit(session, user, "engagement.configured", deal)
    await session.commit()
    return await engagement(opportunity_id, user, session)


@router.post("/opportunities/{opportunity_id}/preview")
async def preview(
    opportunity_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_tcg(user)
    deal = await require_opportunity_access(session, user, opportunity_id)
    return await preview_commercial(session, deal)


@router.post("/opportunities/{opportunity_id}/vendors", status_code=201)
async def add_vendor_link(
    opportunity_id: UUID,
    body: VendorLinkCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_tcg(user)
    require_sales_manage(user)
    deal = await lock_opportunity(session, opportunity_id, body.expected_version)
    agreement = await session.get(VendorAgreement, body.agreement_id)
    if agreement is None:
        raise HTTPException(422, "Vendor agreement not found")
    if agreement.buyer_organization_id != body.payer_organization_id:
        raise HTTPException(422, "The vendor payer must match the agreement's contracting buyer")
    if agreement.effective_from > date.today() or (
        agreement.effective_until and agreement.effective_until < date.today()
    ):
        raise HTTPException(422, "The vendor agreement is not currently effective")
    if body.component_id:
        component = await session.get(SolutionComponent, body.component_id)
        if component is None or component.opportunity_id != deal.id:
            raise HTTPException(422, "Component belongs to another opportunity")
    participant = await session.scalar(
        select(OpportunityParticipant.id).where(
            OpportunityParticipant.opportunity_id == deal.id,
            OpportunityParticipant.organization_id == body.payer_organization_id,
            OpportunityParticipant.active.is_(True),
        )
    )
    if not participant:
        raise HTTPException(422, "The payer must participate in this opportunity")
    provider = await session.scalar(
        select(OpportunityParticipant.id).where(
            OpportunityParticipant.opportunity_id == deal.id,
            OpportunityParticipant.organization_id == agreement.provider_organization_id,
        )
    )
    if not provider:
        session.add(
            OpportunityParticipant(
                opportunity_id=deal.id,
                organization_id=agreement.provider_organization_id,
                access_level="NONE",
            )
        )
    row = OpportunityVendorLink(
        opportunity_id=deal.id, **body.model_dump(exclude={"expected_version"})
    )
    session.add(row)
    deal.commercial_version += 1
    # Existing accepted values remain frozen. A new quotation uses the changed vendor cost.
    await session.flush()
    await audit(session, user, "vendor.linked", row)
    await session.commit()
    await session.refresh(row)
    return row_json(row)


@router.post("/contracts", status_code=201)
async def create_contract(
    body: ContractCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_tcg(user)
    require_sales_manage(user)
    deal = await lock_opportunity(session, body.opportunity_id, body.expected_version)
    parties = set(
        await session.scalars(
            select(OpportunityParticipant.organization_id).where(
                OpportunityParticipant.opportunity_id == deal.id,
                OpportunityParticipant.active.is_(True),
            )
        )
    )
    if (
        body.seller_organization_id == body.buyer_organization_id
        or not {body.seller_organization_id, body.buyer_organization_id} <= parties
    ):
        raise HTTPException(422, "Contracts require two distinct opportunity participants")
    tcg = await tcg_organization(session)
    if deal.engagement_model in {"DIRECT", "REFERRAL"} and body.seller_organization_id != tcg.id:
        raise HTTPException(422, "TCG must be the customer contracting seller")
    if deal.engagement_model in {"DIRECT", "REFERRAL"} and (
        body.buyer_organization_id != deal.customer.organization_id
    ):
        raise HTTPException(422, "The customer must be the contracting buyer")
    if deal.engagement_model == "RESELLER" and body.kind == "WHOLESALE":
        partner = await partner_for_model(session, deal.partner_id, deal.engagement_model)
        if body.seller_organization_id != tcg.id or (
            not partner or body.buyer_organization_id != partner.organization_id
        ):
            raise HTTPException(422, "Wholesale contracts run from TCG to the reseller")
    row = CommercialContract(**body.model_dump(exclude={"expected_version"}))
    session.add(row)
    await session.flush()
    deal.commercial_version += 1
    await audit(session, user, "contract.created", row)
    await session.commit()
    await session.refresh(row)
    return row_json(row)


@router.get("/terms")
async def terms(
    opportunity_id: UUID | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    admin(user)
    statement = select(CommercialTermVersion).order_by(CommercialTermVersion.created_at.desc())
    if opportunity_id:
        contract_ids = select(CommercialContract.id).where(
            CommercialContract.opportunity_id == opportunity_id
        )
        statement = statement.where(
            or_(
                CommercialTermVersion.opportunity_id == opportunity_id,
                CommercialTermVersion.contract_id.in_(contract_ids),
                CommercialTermVersion.scope == "DEFAULT",
            )
        )
    return [row_json(row) for row in await session.scalars(statement)]


async def term_deal(
    session: AsyncSession,
    term: Any,
    expected_version: int | None,
) -> Opportunity | None:
    identifier = term.opportunity_id
    if term.contract_id:
        contract = await session.get(CommercialContract, term.contract_id)
        if contract is None:
            raise HTTPException(422, "Contract not found")
        if contract.status == "ACCEPTED":
            raise HTTPException(
                409, "Create a new amendment contract before changing accepted terms"
            )
        identifier = contract.opportunity_id
    if identifier:
        deal = await lock_opportunity(session, identifier, expected_version)
        if deal.engagement_model != term.engagement_model:
            raise HTTPException(422, "Terms must match the selected engagement model")
        return deal
    return None


@router.post("/terms", status_code=201)
async def create_term(
    body: TermCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    admin(user)
    try:
        validate_parameters(body.engagement_model, body.parameters)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    await term_deal(session, body, body.expected_version)
    if body.partner_agreement_id:
        agreement = await session.get(PartnerAgreement, body.partner_agreement_id)
        if not agreement or agreement.engagement_model != body.engagement_model:
            raise HTTPException(422, "Partner agreement must match the engagement model")
    row = CommercialTermVersion(
        **body.model_dump(exclude={"expected_version", "parameters", "supersedes_id"}),
        parameters=body.parameters.model_dump(mode="json", exclude_none=True),
        supersedes_id=body.supersedes_id,
        created_by_id=user.id,
    )
    session.add(row)
    await session.flush()
    await audit(session, user, "commercial_terms.drafted", row)
    await session.commit()
    await session.refresh(row)
    return row_json(row)


@router.post("/terms/{term_id}/approve")
async def approve_term(
    term_id: UUID,
    body: VersionBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    admin(user)
    row = await session.scalar(
        select(CommercialTermVersion).where(CommercialTermVersion.id == term_id).with_for_update()
    )
    if row is None:
        raise HTTPException(404, "Term version not found")
    if row.status != "DRAFT":
        raise HTTPException(409, "Only draft terms can be approved")
    deal = await term_deal(session, row, body.expected_version)
    key = (
        f"terms:{row.engagement_model}:{row.scope}:{row.partner_agreement_id}:"
        f"{row.opportunity_id}:{row.contract_id}:{row.sku_id}"
    )
    await advisory_scope_lock(session, key)
    same_scope = (
        CommercialTermVersion.engagement_model == row.engagement_model,
        CommercialTermVersion.scope == row.scope,
        CommercialTermVersion.partner_agreement_id == row.partner_agreement_id,
        CommercialTermVersion.opportunity_id == row.opportunity_id,
        CommercialTermVersion.contract_id == row.contract_id,
        CommercialTermVersion.sku_id == row.sku_id,
    )
    old = None
    if row.supersedes_id:
        old = await session.scalar(
            select(CommercialTermVersion)
            .where(CommercialTermVersion.id == row.supersedes_id, *same_scope)
            .with_for_update()
        )
        if old is None or old.status != "APPROVED" or row.effective_from <= old.effective_from:
            raise HTTPException(
                422, "Supersede an approved version in the same scope at a later date"
            )
        # Never backdate a superseding version over already finalized transactions.
        if row.effective_from < date.today():
            raise HTTPException(422, "Superseding terms cannot be backdated")
    conflicts = list(
        await session.scalars(
            select(CommercialTermVersion).where(
                *same_scope,
                CommercialTermVersion.id != row.id,
                CommercialTermVersion.status.in_(["APPROVED", "SUPERSEDED"]),
                CommercialTermVersion.effective_from <= (row.effective_until or date.max),
                or_(
                    CommercialTermVersion.effective_until.is_(None),
                    CommercialTermVersion.effective_until >= row.effective_from,
                ),
            )
        )
    )
    if any(conflict.id != row.supersedes_id for conflict in conflicts):
        raise HTTPException(409, "Overlapping terms of equal specificity are not allowed")
    if old:
        old.effective_until = row.effective_from - timedelta(days=1)
        old.status = "SUPERSEDED"
        row.version = old.version + 1
    row.status, row.approved_by_id = "APPROVED", user.id
    if deal:
        deal.commercial_version += 1
        if deal.approval_status == "APPROVED":
            deal.approval_status = "DRAFT"
            deal.review_reason = "Approved commercial changes require opportunity reapproval"
            deal.approved_at = None
            deal.protection_expires_at = None
    await audit(session, user, "commercial_terms.approved", row)
    await session.commit()
    await session.refresh(row)
    return row_json(row)


@router.get("/opportunities/{opportunity_id}/snapshots")
async def snapshots(
    opportunity_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    await require_opportunity_access(session, user, opportunity_id)
    organization_id = await user_organization(session, user)
    rows = list(
        await session.scalars(
            select(CommercialSnapshot)
            .where(CommercialSnapshot.opportunity_id == opportunity_id)
            .order_by(CommercialSnapshot.created_at.desc())
        )
    )
    if is_tcg_user(user):
        return [row_json(row) for row in rows]
    result = []
    for row in rows:
        amounts = row.payload.get("result", {})
        if not isinstance(amounts, dict):
            continue
        allocations = amounts.get("allocations", {})
        if not isinstance(allocations, dict):
            continue
        result.append(
            {
                "id": str(row.id),
                "revision": row.revision,
                "status": "SNAPSHOTTED",
                "own_entitlement": allocations.get(str(organization_id)),
                "engagement_model": row.payload.get("engagement_model"),
            }
        )
    return result


@router.post("/opportunities/{opportunity_id}/conversion")
async def record_conversion(
    opportunity_id: UUID,
    body: ConversionCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_tcg(user)
    require_sales_manage(user)
    deal = await lock_opportunity(session, opportunity_id, body.expected_version)
    frozen = await session.get(CommercialSnapshot, body.snapshot_id)
    if frozen is None or frozen.opportunity_id != deal.id:
        raise HTTPException(422, "Select a commercial snapshot from this opportunity")
    quote = await session.get(Quote, frozen.quote_id)
    if (
        quote is None
        or quote.status not in {"FINAL", "ACCEPTED"}
        or (quote.current_revision != frozen.revision)
    ):
        raise HTTPException(422, "Conversion requires a current finalized or accepted revision")
    existing = await session.scalar(
        select(ConversionEvidence).where(ConversionEvidence.opportunity_id == deal.id)
    )
    actual = body.actual_eligibility.model_dump(mode="json") if body.actual_eligibility else None
    if existing:
        if existing.snapshot_id != body.snapshot_id or existing.actual_eligibility != actual:
            raise HTTPException(409, "Conversion already recorded; use a referenced adjustment")
    else:
        existing = ConversionEvidence(
            opportunity_id=deal.id,
            snapshot_id=frozen.id,
            evidence=body.evidence,
            actual_eligibility=actual,
            recorded_by_id=user.id,
        )
        session.add(existing)
        await session.flush()
    accrual = await accrue_conversion(session, deal)
    await audit(session, user, "conversion.recorded", existing)
    await session.commit()
    return {
        "conversion_id": str(existing.id),
        "accrual": row_json(accrual) if accrual else None,
        "status": "ACCRUED" if accrual else "AWAITING_QUALIFYING_WIN",
    }


@router.get("/commissions")
async def commissions(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    statement = select(CommissionAccrual).order_by(CommissionAccrual.created_at.desc())
    if not is_tcg_user(user):
        organization = await user_organization(session, user)
        if organization is None:
            return []
        statement = statement.where(
            CommissionAccrual.beneficiary_id == organization,
            CommissionAccrual.opportunity_id.in_(visible_opportunity_ids(user)),
        )
    result = []
    for row in await session.scalars(statement):
        adjustments = list(
            await session.scalars(
                select(CommissionAdjustment).where(CommissionAdjustment.accrual_id == row.id)
            )
        )
        payments = list(
            await session.scalars(
                select(CommissionPayment).where(CommissionPayment.accrual_id == row.id)
            )
        )
        balance = row.amount + sum((a.amount for a in adjustments), Decimal("0"))
        paid = sum((p.amount for p in payments), Decimal("0"))
        result.append(
            row_json(row)
            | {
                "adjustments": [row_json(a) for a in adjustments],
                "payments": [row_json(p) for p in payments],
                "net_accrued": str(balance),
                "paid": str(paid),
                "outstanding": str(balance - paid),
                "status": "PAID" if paid >= balance and paid > 0 else "ACCRUED",
                "version": len(payments) + len(adjustments),
            }
        )
    return result


@router.post("/commissions/{accrual_id}/adjustments", status_code=201)
async def adjust_commission(
    accrual_id: UUID,
    body: AccrualAdjustmentCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    admin(user)
    accrual = await session.scalar(
        select(CommissionAccrual).where(CommissionAccrual.id == accrual_id).with_for_update()
    )
    if accrual is None:
        raise HTTPException(404, "Accrual not found")
    previous = await session.scalar(
        select(CommissionAdjustment).where(
            CommissionAdjustment.accrual_id == accrual_id,
            CommissionAdjustment.event_key == body.event_key,
        )
    )
    if previous:
        if previous.amount != body.amount or previous.reason != body.reason:
            raise HTTPException(409, "Adjustment event key already has different contents")
        return row_json(previous)
    if not accrual.settlement_policy:
        raise HTTPException(422, "An agreed settlement/refund policy is required for adjustments")
    row = CommissionAdjustment(accrual_id=accrual_id, created_by_id=user.id, **body.model_dump())
    session.add(row)
    await session.flush()
    await audit(session, user, "commission.adjusted", row)
    await session.commit()
    await session.refresh(row)
    return row_json(row)


@router.post("/commissions/{accrual_id}/payments", status_code=201)
async def record_payment(
    accrual_id: UUID,
    body: SettlementCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    admin(user)
    accrual = await session.scalar(
        select(CommissionAccrual).where(CommissionAccrual.id == accrual_id).with_for_update()
    )
    if accrual is None:
        raise HTTPException(404, "Accrual not found")
    if not accrual.settlement_policy:
        raise HTTPException(422, "No settlement policy is agreed; automatic payout is not allowed")
    previous = await session.scalar(
        select(CommissionPayment).where(
            CommissionPayment.accrual_id == accrual_id,
            CommissionPayment.payment_reference == body.payment_reference,
        )
    )
    if previous:
        if previous.amount != body.amount:
            raise HTTPException(409, "Payment reference already has a different amount")
        return row_json(previous)
    adjustment_rows = list(
        await session.scalars(
            select(CommissionAdjustment).where(CommissionAdjustment.accrual_id == accrual_id)
        )
    )
    payment_rows = list(
        await session.scalars(
            select(CommissionPayment).where(CommissionPayment.accrual_id == accrual_id)
        )
    )
    if body.expected_version != len(adjustment_rows) + len(payment_rows):
        raise HTTPException(409, "Commission ledger changed. Reload before recording payment.")
    outstanding = (
        accrual.amount
        + sum((r.amount for r in adjustment_rows), Decimal("0"))
        - sum((r.amount for r in payment_rows), Decimal("0"))
    )
    if body.amount <= 0 or body.amount > outstanding:
        raise HTTPException(
            422, "Payment must be positive and no greater than the outstanding balance"
        )
    row = CommissionPayment(
        accrual_id=accrual_id,
        payment_reference=body.payment_reference,
        amount=body.amount,
        recorded_by_id=user.id,
    )
    session.add(row)
    await session.flush()
    await audit(session, user, "commission.payment_recorded", row)
    await session.commit()
    await session.refresh(row)
    return row_json(row)


@router.get("/summary")
async def commercial_summary(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_tcg(user)
    latest: dict[UUID, CommercialSnapshot] = {}
    for snapshot in await session.scalars(
        select(CommercialSnapshot).order_by(CommercialSnapshot.created_at.desc())
    ):
        latest.setdefault(snapshot.opportunity_id, snapshot)
    names = (
        "customer_value",
        "tcg_entitlement",
        "partner_entitlement",
        "vendor_cost",
        "commission_expense",
    )
    totals = {name: Decimal("0") for name in names}
    undisclosed = {name: 0 for name in names}
    for snapshot in latest.values():
        amounts = snapshot.payload.get("result", {})
        if not isinstance(amounts, dict):
            continue
        for name in names:
            value = amounts.get(name)
            if value is None:
                undisclosed[name] += 1
            else:
                totals[name] += Decimal(str(value))
    return {
        "basis": "Latest finalized forecast per opportunity",
        "opportunities": len(latest),
        "totals": {key: str(value) for key, value in totals.items()},
        "undisclosed": undisclosed,
    }
