from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.commercial import calculate_commercial, money, resolve_parameter_layers
from app.models.commercial import (
    CommercialContract,
    CommercialSnapshot,
    CommercialTermVersion,
    CommissionAccrual,
    ConversionEvidence,
    OpportunityParticipant,
    OpportunityRole,
    OpportunityVendorLink,
    Organization,
    PartnerAgreement,
    SolutionComponent,
)
from app.models.identity import User
from app.models.partner import Partner, PartnerStatus
from app.models.pricing import Product, ProductPrice, Sku
from app.models.sales import Opportunity, Quote
from app.schemas.commercial import (
    CalculationRequest,
    CommercialParameters,
    ComponentInput,
    EngagementModel,
    EngagementUpdate,
    ParticipantInput,
    RoleInput,
    VendorCost,
)

SCOPE_RANK = {"DEFAULT": 1, "PARTNER": 2, "OPPORTUNITY": 3, "CONTRACT": 4}


def row_json(row: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for column in row.__table__.columns:
        value = getattr(row, column.name)
        if isinstance(value, (UUID, Decimal)):
            value = str(value)
        elif hasattr(value, "isoformat"):
            value = value.isoformat()
        result[column.name] = value
    return result


async def tcg_organization(session: AsyncSession) -> Organization:
    organization = await session.scalar(
        select(Organization).where(Organization.identifier == "TCG_INTERNAL")
    )
    if organization is None:
        raise HTTPException(409, "Apply the commercial migration and seeds first")
    return organization


async def lock_opportunity(
    session: AsyncSession,
    opportunity_id: UUID,
    expected_version: int | None = None,
) -> Opportunity:
    deal = await session.scalar(
        select(Opportunity)
        .where(Opportunity.id == opportunity_id)
        .with_for_update(of=Opportunity)
        .execution_options(populate_existing=True)
    )
    if deal is None:
        raise HTTPException(404, "Opportunity not found")
    if expected_version is not None and deal.commercial_version != expected_version:
        raise HTTPException(409, "Commercial data changed. Reload before saving.")
    return deal


async def partner_for_model(
    session: AsyncSession,
    partner_id: UUID | None,
    model: str,
) -> Partner | None:
    if partner_id is None:
        if model != "DIRECT":
            raise HTTPException(422, "An active commercial partner is required")
        return None
    partner = await session.get(Partner, partner_id)
    if partner is None or partner.status != PartnerStatus.ACTIVE or not partner.organization_id:
        raise HTTPException(422, "An active partner with an organization is required")
    if model != "DIRECT" and model not in {p.code for p in partner.capabilities}:
        raise HTTPException(422, "The partner does not have this engagement capability")
    return partner


async def initialize_engagement(
    session: AsyncSession,
    deal: Opportunity,
    model: str,
    user: User,
) -> None:
    tcg = await tcg_organization(session)
    partner = await partner_for_model(session, deal.partner_id, model)
    if deal.customer.organization_id is None:
        organization = Organization(
            legal_name=deal.customer.legal_name or deal.customer.name,
            identifier=f"customer:{deal.customer.id}",
        )
        session.add(organization)
        await session.flush()
        deal.customer.organization_id = organization.id
    customer_org = deal.customer.organization_id
    parties = [
        ParticipantInput(organization_id=tcg.id),
        ParticipantInput(organization_id=customer_org),
    ]
    if partner:
        parties.append(
            ParticipantInput(
                organization_id=partner.organization_id,
                capability=model if model != "DIRECT" else partner.capabilities[0].code,
                access_level="PROGRESS" if model in {"REFERRAL", "DIRECT"} else "COMMERCIAL",
            )
        )
    product = await session.get(Product, deal.product_id)
    product_owner = (
        product.owner_organization_id if product and product.owner_organization_id else tcg.id
    )
    if product_owner not in {p.organization_id for p in parties}:
        parties.append(ParticipantInput(organization_id=product_owner))
    parties = list({p.organization_id: p for p in parties}.values())
    roles: list[RoleInput] = []
    owner = partner.organization_id if model == "RESELLER" and partner else tcg.id
    if model != "SYSTEM_INTEGRATOR":
        for role in (
            "CUSTOMER_RELATIONSHIP_OWNER",
            "BIDDER",
            "CONTRACTING_SELLER",
            "DELIVERY_LEAD",
        ):
            roles.append(RoleInput.model_validate({"organization_id": owner, "role": role}))
    roles.extend(
        [
            RoleInput(organization_id=tcg.id, role="MCUBE_SELLER"),
            RoleInput(organization_id=product_owner, role="PRODUCT_OWNER"),
            RoleInput(organization_id=customer_org, role="BILL_TO"),
        ]
    )
    if model == "REFERRAL" and partner:
        roles.append(RoleInput(organization_id=partner.organization_id, role="REFERRER"))
    await apply_engagement(
        session,
        deal,
        EngagementUpdate(
            expected_version=deal.commercial_version,
            engagement_model=EngagementModel(model),
            partner_id=deal.partner_id,
            responsible_user_id=user.id if user.partner_id is None else None,
            participants=parties,
            roles=roles,
            components=[
                ComponentInput(
                    name=deal.name,
                    product_id=deal.product_id,
                    owner_organization_id=product_owner,
                    seller_organization_id=tcg.id,
                    delivery_organization_id=owner,
                    billing_organization_id=customer_org,
                    amount=deal.estimated_value,
                )
            ],
        ),
    )


async def apply_engagement(
    session: AsyncSession,
    deal: Opportunity,
    body: EngagementUpdate,
) -> None:
    if deal.commercial_version != body.expected_version:
        raise HTTPException(409, "Commercial data changed. Reload before saving.")
    partner = await partner_for_model(session, body.partner_id, body.engagement_model)
    org_ids = {p.organization_id for p in body.participants}
    if len(org_ids) != len(body.participants):
        raise HTTPException(422, "Each organization may participate only once")
    if partner and partner.organization_id not in org_ids:
        raise HTTPException(422, "The commercial partner must be a participant")
    if body.responsible_user_id:
        responsible = await session.get(User, body.responsible_user_id)
        from app.domain.access import is_tcg_user

        if responsible is None or not responsible.is_active or not is_tcg_user(responsible):
            raise HTTPException(422, "The internal responsible user must be an active TCG user")
    organizations = list(
        await session.scalars(
            select(Organization).where(
                Organization.id.in_(org_ids), Organization.is_active.is_(True)
            )
        )
    )
    if len(organizations) != len(org_ids):
        raise HTTPException(422, "Every participant must be an active organization")
    for proposed_participant in body.participants:
        associated = await session.scalar(
            select(Partner).where(Partner.organization_id == proposed_participant.organization_id)
        )
        if proposed_participant.capability:
            if associated is None or associated.status != PartnerStatus.ACTIVE:
                raise HTTPException(422, "A commercial capability requires an active partner")
            if proposed_participant.capability not in {c.code for c in associated.capabilities}:
                raise HTTPException(422, "Participant capability is not approved for this partner")
        if proposed_participant.access_level != "NONE" and not proposed_participant.capability:
            raise HTTPException(
                422, "Vendor/customer participation alone cannot grant portal access"
            )
        if (
            proposed_participant.capability == "REFERRAL"
            and proposed_participant.access_level == "COMMERCIAL"
        ):
            raise HTTPException(422, "Referral participants cannot access customer commercials")
    primary_keys: set[tuple[str, str]] = set()
    for role in body.roles:
        if role.organization_id not in org_ids:
            raise HTTPException(422, "Every role must reference a participant in this opportunity")
        role_key = (role.role, role.scope)
        if role.primary and role_key in primary_keys:
            raise HTTPException(422, "A role may have only one primary party per scope")
        if role.primary:
            primary_keys.add(role_key)
    accepted = await session.scalar(
        select(CommercialContract.id).where(
            CommercialContract.opportunity_id == deal.id, CommercialContract.status == "ACCEPTED"
        )
    )
    if accepted and not body.amendment_reason:
        raise HTTPException(409, "An accepted contract requires an explicit amendment reason")
    existing_components = list(
        await session.scalars(
            select(SolutionComponent).where(SolutionComponent.opportunity_id == deal.id)
        )
    )
    component_map = {c.id: c for c in existing_components}
    retained_ids = {c.id for c in body.components if c.id}
    if len(retained_ids) != sum(c.id is not None for c in body.components):
        raise HTTPException(422, "Component IDs must be unique")
    if any(identifier not in component_map for identifier in retained_ids):
        raise HTTPException(422, "Component does not belong to this opportunity")
    if existing_components and set(component_map) - retained_ids:
        raise HTTPException(422, "Retain existing component IDs to preserve commercial references")
    for component in body.components:
        values = component.model_dump(exclude={"id"})
        party_fields = (
            "owner_organization_id",
            "seller_organization_id",
            "delivery_organization_id",
            "billing_organization_id",
        )
        if any(values[key] not in org_ids for key in party_fields):
            raise HTTPException(422, "Component roles must reference opportunity participants")
        if component.product_id:
            product = await session.get(Product, component.product_id)
            if product is None or not product.is_active:
                raise HTTPException(422, "Unknown or inactive product")
            if (
                product.owner_organization_id
                and product.owner_organization_id != component.owner_organization_id
            ):
                raise HTTPException(422, "The component owner must match the product owner")
        if component.sku_id:
            sku = await session.get(Sku, component.sku_id)
            if sku is None or sku.product_id != component.product_id or not sku.is_active:
                raise HTTPException(422, "SKU must belong to the selected active product")
        if component.id:
            for key, value in values.items():
                setattr(component_map[component.id], key, value)
        else:
            session.add(SolutionComponent(opportunity_id=deal.id, **values))
    await session.execute(delete(OpportunityRole).where(OpportunityRole.opportunity_id == deal.id))
    existing = list(
        await session.scalars(
            select(OpportunityParticipant).where(OpportunityParticipant.opportunity_id == deal.id)
        )
    )
    mapping = {p.organization_id: p for p in existing}
    for existing_participant in existing:
        if existing_participant.organization_id not in org_ids:
            existing_participant.active = False
            existing_participant.access_level = "NONE"
    for entry in body.participants:
        participant = mapping.get(entry.organization_id)
        if participant is None:
            participant = OpportunityParticipant(opportunity_id=deal.id, **entry.model_dump())
            session.add(participant)
            mapping[entry.organization_id] = participant
        else:
            for key, value in entry.model_dump().items():
                setattr(participant, key, value)
    await session.flush()
    for role in body.roles:
        session.add(
            OpportunityRole(
                opportunity_id=deal.id,
                participant_id=mapping[role.organization_id].id,
                role=role.role,
                scope=role.scope,
                is_primary=role.primary,
            )
        )
    deal.engagement_model = body.engagement_model
    deal.partner_id = body.partner_id
    deal.responsible_user_id = body.responsible_user_id
    deal.migration_review_required = False
    deal.commercial_version += 1
    if deal.approval_status == "APPROVED":
        deal.approval_status = "DRAFT"
        deal.review_reason = body.amendment_reason or "Commercial changes require reapproval"
        deal.approved_at = None
        deal.protection_expires_at = None
    await session.flush()


async def validate_engagement(session: AsyncSession, deal: Opportunity) -> None:
    if deal.migration_review_required or deal.engagement_model is None:
        raise HTTPException(409, "This legacy opportunity needs commercial classification")
    tcg = await tcg_organization(session)
    partner = await partner_for_model(session, deal.partner_id, deal.engagement_model)
    participants = list(
        await session.scalars(
            select(OpportunityParticipant).where(
                OpportunityParticipant.opportunity_id == deal.id,
                OpportunityParticipant.active.is_(True),
            )
        )
    )
    by_id = {p.id: p for p in participants}
    roles = list(
        await session.scalars(
            select(OpportunityRole).where(
                OpportunityRole.opportunity_id == deal.id,
                OpportunityRole.scope == "OPPORTUNITY",
                OpportunityRole.is_primary.is_(True),
            )
        )
    )
    assigned = {
        r.role: by_id[r.participant_id].organization_id for r in roles if r.participant_id in by_id
    }
    required = {
        "CUSTOMER_RELATIONSHIP_OWNER",
        "BIDDER",
        "CONTRACTING_SELLER",
        "MCUBE_SELLER",
        "DELIVERY_LEAD",
    }
    if not required <= assigned.keys():
        raise HTTPException(
            422, "Assign customer owner, bidder, seller, mcube seller, and delivery lead"
        )
    if deal.engagement_model in {"DIRECT", "REFERRAL"}:
        expected = (
            required
            if deal.engagement_model == "REFERRAL"
            else {"CUSTOMER_RELATIONSHIP_OWNER", "BIDDER", "CONTRACTING_SELLER"}
        )
        if any(assigned[r] != tcg.id for r in expected):
            raise HTTPException(422, "TCG must own the required roles for this engagement")
    if deal.engagement_model == "RESELLER" and partner:
        if any(
            assigned[r] != partner.organization_id
            for r in ("CUSTOMER_RELATIONSHIP_OWNER", "CONTRACTING_SELLER", "BIDDER")
        ):
            raise HTTPException(422, "The reseller must own its customer commercial relationship")
    if deal.engagement_model == "REFERRAL" and partner:
        if assigned.get("REFERRER") != partner.organization_id:
            raise HTTPException(422, "The referral must be attributed to the referral participant")
    if partner and deal.engagement_model != "DIRECT":
        if not any(
            p.organization_id == partner.organization_id and p.capability == deal.engagement_model
            for p in participants
        ):
            raise HTTPException(422, "The required active commercial participant is missing")
    if not await session.scalar(
        select(SolutionComponent.id).where(SolutionComponent.opportunity_id == deal.id).limit(1)
    ):
        raise HTTPException(422, "At least one solution component is required")


async def resolve_terms(
    session: AsyncSession,
    model: str,
    *,
    opportunity_id: UUID | None = None,
    partner_id: UUID | None = None,
    contract_id: UUID | None = None,
    sku_id: UUID | None = None,
    as_of: date | None = None,
) -> tuple[CommercialParameters, dict[str, str]]:
    today = as_of or date.today()
    agreement_ids = select(PartnerAgreement.id).where(
        PartnerAgreement.partner_id == partner_id,
        PartnerAgreement.engagement_model == model,
        PartnerAgreement.status == "APPROVED",
        PartnerAgreement.effective_from <= today,
        or_(PartnerAgreement.effective_until.is_(None), PartnerAgreement.effective_until >= today),
    )
    scopes = [CommercialTermVersion.scope == "DEFAULT"]
    if partner_id:
        scopes.append(CommercialTermVersion.partner_agreement_id.in_(agreement_ids))
    if opportunity_id:
        scopes.append(CommercialTermVersion.opportunity_id == opportunity_id)
    if contract_id:
        scopes.append(CommercialTermVersion.contract_id == contract_id)
    rows = list(
        await session.scalars(
            select(CommercialTermVersion).where(
                CommercialTermVersion.engagement_model == model,
                CommercialTermVersion.status.in_(["APPROVED", "SUPERSEDED"]),
                CommercialTermVersion.effective_from <= today,
                or_(
                    CommercialTermVersion.effective_until.is_(None),
                    CommercialTermVersion.effective_until >= today,
                ),
                or_(*scopes),
                or_(CommercialTermVersion.sku_id.is_(None), CommercialTermVersion.sku_id == sku_id)
                if sku_id
                else CommercialTermVersion.sku_id.is_(None),
            )
        )
    )
    layers = [
        (
            SCOPE_RANK[row.scope] * 2 + (1 if row.sku_id else 0),
            f"term:{row.id}:v{row.version}",
            CommercialParameters.model_validate(row.parameters),
        )
        for row in rows
    ]
    try:
        return resolve_parameter_layers(layers)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


async def resolve_unit_price(
    session: AsyncSession,
    model: str,
    sku_id: UUID,
    *,
    deal: Opportunity | None = None,
    partner_id: UUID | None = None,
    contract_id: UUID | None = None,
    as_of: date | None = None,
) -> tuple[Decimal, dict[str, Any]]:
    today = as_of or date.today()
    sku = await session.get(Sku, sku_id)
    if sku is None or not sku.is_active:
        raise HTTPException(422, "Unknown or inactive SKU")
    params, sources = await resolve_terms(
        session,
        model,
        opportunity_id=deal.id if deal else None,
        partner_id=deal.partner_id if deal else partner_id,
        contract_id=contract_id,
        sku_id=sku_id,
        as_of=today,
    )
    prices = list(
        await session.scalars(
            select(ProductPrice).where(
                ProductPrice.sku_id == sku_id,
                ProductPrice.is_active.is_(True),
                ProductPrice.effective_from <= today,
                or_(ProductPrice.effective_until.is_(None), ProductPrice.effective_until >= today),
            )
        )
    )
    if len(prices) > 1:
        raise HTTPException(409, "Overlapping active catalog prices require review")
    if params.fixed_unit_price is not None:
        amount = params.fixed_unit_price
    else:
        if not prices:
            raise HTTPException(422, "No applicable catalog price or explicit fixed price")
        base = prices[0].amount
        amount = money(base * (Decimal("100") - (params.discount_percentage or Decimal("0"))) / 100)
        sources["catalog_price"] = f"catalog:{prices[0].id}"
    return money(amount), {
        "as_of": today.isoformat(),
        "engagement_model": model,
        "sources": sources,
        "resolved_unit_price": str(money(amount)),
        "parameters": params.model_dump(mode="json"),
    }


async def preview_commercial(
    session: AsyncSession,
    deal: Opportunity,
    *,
    quote: Quote | None = None,
) -> dict[str, Any]:
    await validate_engagement(session, deal)
    tcg = await tcg_organization(session)
    partner = await partner_for_model(session, deal.partner_id, deal.engagement_model or "")
    params, sources = await resolve_terms(
        session,
        deal.engagement_model or "",
        opportunity_id=deal.id,
        partner_id=deal.partner_id,
        contract_id=quote.contract_id if quote else None,
    )
    if quote:
        if deal.engagement_model == "RESELLER":
            if params.wholesale_value is not None and params.wholesale_value != quote.total:
                raise HTTPException(422, "Quote total must match the agreed wholesale value")
            params = params.model_copy(update={"wholesale_value": quote.total})
        elif deal.engagement_model != "SYSTEM_INTEGRATOR":
            if params.customer_value is not None and params.customer_value != quote.total:
                raise HTTPException(422, "Quote total must match the customer commercial value")
            params = params.model_copy(update={"customer_value": quote.total})
    components = list(
        await session.scalars(
            select(SolutionComponent).where(SolutionComponent.opportunity_id == deal.id)
        )
    )
    component_ids = {c.id for c in components}
    scoped = []
    if params.eligibility:
        scoped.extend(params.eligibility.component_ids)
    if params.pool:
        scoped.extend(params.pool.component_ids)
    if any(identifier not in component_ids for identifier in scoped):
        raise HTTPException(422, "Commercial basis includes components from another opportunity")
    vendor_links = list(
        await session.scalars(
            select(OpportunityVendorLink).where(OpportunityVendorLink.opportunity_id == deal.id)
        )
    )
    if params.pool:
        deducted = set(params.pool.deducted_vendor_link_ids)
        if deducted != {v.id for v in vendor_links if v.cost_treatment == "POOL_DEDUCTION"}:
            raise HTTPException(
                422, "Pool deductions must match the explicitly scoped vendor costs"
            )
    if params.compensation_beneficiary_id:
        participant = await session.scalar(
            select(OpportunityParticipant.id).where(
                OpportunityParticipant.opportunity_id == deal.id,
                OpportunityParticipant.organization_id == params.compensation_beneficiary_id,
                OpportunityParticipant.active.is_(True),
            )
        )
        beneficiary = await session.scalar(
            select(Partner.id).where(
                Partner.organization_id == params.compensation_beneficiary_id,
                Partner.status == PartnerStatus.ACTIVE,
            )
        )
        if not participant or not beneficiary:
            raise HTTPException(422, "Compensation needs an active associated partner beneficiary")
    request = CalculationRequest(
        engagement_model=EngagementModel(deal.engagement_model or ""),
        tcg_organization_id=tcg.id,
        partner_organization_id=partner.organization_id if partner else None,
        parameters=params,
        approved=bool(sources),
        vendor_costs=[
            VendorCost(link_id=v.id, payer_id=v.payer_organization_id, amount=v.amount)
            for v in vendor_links
        ],
    )
    try:
        result = calculate_commercial(request)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if (
        quote
        and deal.engagement_model == "SYSTEM_INTEGRATOR"
        and quote.total != result.tcg_entitlement
    ):
        raise HTTPException(422, "The TCG quote must match the agreed TCG allocation")
    if deal.engagement_model == "RESELLER" and quote:
        has_terms = "wholesale_value" in sources
        for item in quote.items:
            item_sources = item.pricing_snapshot.get("sources", {})
            if isinstance(item_sources, dict):
                has_terms = has_terms or any(
                    str(source).startswith("term:") for source in item_sources.values()
                )
        if not has_terms:
            raise HTTPException(422, "Explicit agreed wholesale terms are required")
    participants = list(
        await session.scalars(
            select(OpportunityParticipant).where(OpportunityParticipant.opportunity_id == deal.id)
        )
    )
    roles = list(
        await session.scalars(
            select(OpportunityRole).where(OpportunityRole.opportunity_id == deal.id)
        )
    )
    return {
        "engagement_model": deal.engagement_model,
        "engagement_version": deal.commercial_version,
        "request": request.model_dump(mode="json"),
        "result": result.model_dump(mode="json"),
        "sources": sources,
        "participants": [row_json(p) for p in participants],
        "roles": [row_json(r) for r in roles],
        "components": [row_json(c) for c in components],
        "vendor_links": [row_json(v) for v in vendor_links],
    }


async def freeze_commercial(
    session: AsyncSession,
    deal: Opportunity,
    quote: Quote,
) -> CommercialSnapshot:
    for item in quote.items:
        amount, current = await resolve_unit_price(
            session,
            deal.engagement_model or "",
            item.sku_id,
            deal=deal,
            contract_id=quote.contract_id,
        )
        if amount != item.unit_price or current["sources"] != item.pricing_snapshot.get("sources"):
            raise HTTPException(
                409, "Draft item prices changed. Remove and re-add the items before finalizing."
            )
    payload = await preview_commercial(session, deal, quote=quote)
    frozen = CommercialSnapshot(
        opportunity_id=deal.id,
        quote_id=quote.id,
        revision=quote.current_revision,
        engagement_version=deal.commercial_version,
        payload=payload,
    )
    session.add(frozen)
    await session.flush()
    return frozen


async def accrue_conversion(session: AsyncSession, deal: Opportunity) -> CommissionAccrual | None:
    # Caller holds the opportunity row lock. A unique event key also protects retries.
    if deal.stage != "WON":
        return None
    evidence = await session.scalar(
        select(ConversionEvidence).where(ConversionEvidence.opportunity_id == deal.id)
    )
    if evidence is None:
        return None
    frozen = await session.get(CommercialSnapshot, evidence.snapshot_id)
    if frozen is None:
        raise HTTPException(409, "Conversion snapshot is unavailable")
    request = CalculationRequest.model_validate(frozen.payload["request"])
    if request.engagement_model != "REFERRAL" and (
        request.engagement_model != "DIRECT"
        or request.parameters.compensation_beneficiary_id is None
    ):
        return None
    from app.schemas.commercial import Eligibility

    if evidence.actual_eligibility is None:
        raise HTTPException(422, "Actual eligible revenue must be recorded before accrual")
    actual = Eligibility.model_validate(evidence.actual_eligibility)
    forecast = request.parameters.eligibility
    if forecast is None or set(actual.component_ids) != set(forecast.component_ids):
        raise HTTPException(422, "Actual eligibility must use the snapshotted component scope")
    treatments = ("discounts", "taxes", "vendor_charges", "credits", "refunds")
    if any(getattr(actual, k) != getattr(forecast, k) for k in treatments):
        raise HTTPException(422, "Actual eligibility must preserve the agreed revenue treatments")
    if deal.actual_contract_value is None or actual.amount > deal.actual_contract_value:
        raise HTTPException(422, "Actual eligible revenue exceeds the actual customer value")
    beneficiary = (
        request.partner_organization_id
        if request.engagement_model == "REFERRAL"
        else (request.parameters.compensation_beneficiary_id)
    )
    rate = request.parameters.referral_rate
    if request.engagement_model == "DIRECT":
        rate = request.parameters.compensation_rate
    elif rate is None:
        rate = Decimal("10")
    if beneficiary is None or rate is None:
        raise HTTPException(422, "The snapshotted beneficiary and rate are required")
    event = f"conversion:{deal.id}"
    existing = await session.scalar(
        select(CommissionAccrual).where(
            CommissionAccrual.qualifying_event == event,
            CommissionAccrual.beneficiary_id == beneficiary,
        )
    )
    if existing:
        return existing
    accrual = CommissionAccrual(
        opportunity_id=deal.id,
        snapshot_id=frozen.id,
        beneficiary_id=beneficiary,
        qualifying_event=event,
        eligible_amount=actual.amount,
        rate=rate,
        amount=money(actual.amount * rate / 100),
        settlement_policy=request.parameters.settlement_policy,
    )
    session.add(accrual)
    await session.flush()
    return accrual


async def advisory_scope_lock(session: AsyncSession, key: str) -> None:
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": key}
        )
