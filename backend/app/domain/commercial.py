"""Pure decimal commercial calculations. No database state or tier pricing."""

from decimal import ROUND_HALF_UP, Decimal

from app.schemas.commercial import (
    CalculationRequest,
    CalculationResult,
    CommercialParameters,
    EngagementModel,
)

ZERO = Decimal("0")
HUNDRED = Decimal("100")


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def validate_parameters(model: EngagementModel, p: CommercialParameters) -> None:
    si_fields = (p.pool, p.tcg_percentage, p.tcg_fixed, p.allocations, p.allocation_method)
    if model != EngagementModel.SYSTEM_INTEGRATOR and any(v is not None for v in si_fields):
        raise ValueError("SI allocations are only valid for System Integrator engagements")
    if model != EngagementModel.REFERRAL and p.referral_rate is not None:
        raise ValueError("Referral allocations are invalid for this engagement model")
    if model != EngagementModel.DIRECT and (
        p.compensation_rate is not None or p.compensation_beneficiary_id is not None
    ):
        raise ValueError("Additional compensation is only valid for Direct engagements")
    if model != EngagementModel.RESELLER and (
        p.wholesale_value is not None or p.customer_selling_value is not None
    ):
        raise ValueError("Wholesale and resale values require a Reseller engagement")


def calculate_commercial(request: CalculationRequest) -> CalculationResult:
    p, model = request.parameters, request.engagement_model
    validate_parameters(model, p)
    tcg, partner = str(request.tcg_organization_id), str(request.partner_organization_id)
    if model != EngagementModel.DIRECT and request.partner_organization_id is None:
        raise ValueError("This engagement requires an explicit partner beneficiary")
    if request.partner_organization_id == request.tcg_organization_id:
        raise ValueError("TCG and the external partner must be different organizations")
    costs = {c.link_id: c for c in request.vendor_costs}
    if len(costs) != len(request.vendor_costs):
        raise ValueError("A vendor cost cannot be counted twice")
    by_payer: dict[str, Decimal] = {}
    for cost in costs.values():
        payer = str(cost.payer_id)
        by_payer[payer] = money(by_payer.get(payer, ZERO) + cost.amount)
    result = CalculationResult(
        customer_value=p.customer_value,
        tcg_entitlement=ZERO,
        partner_entitlement=ZERO,
        vendor_cost=money(sum((c.amount for c in costs.values()), ZERO)),
        commission_expense=ZERO,
        allocations={},
        vendor_costs_by_payer=by_payer,
    )
    if model == EngagementModel.RESELLER:
        if p.wholesale_value is None:
            raise ValueError("An agreed wholesale value is required")
        result.partner_entitlement = None
        result.customer_value = p.customer_selling_value
        result.tcg_entitlement = p.wholesale_value
        if p.customer_selling_value is not None:
            result.reseller_gross_margin = money(p.customer_selling_value - p.wholesale_value)
            result.partner_entitlement = result.reseller_gross_margin
        result.allocations = {tcg: money(p.wholesale_value)}
        if result.reseller_gross_margin is not None:
            result.allocations[partner] = result.reseller_gross_margin
        return result
    if p.customer_value is None:
        raise ValueError("The customer commercial value is required")
    result.tcg_entitlement = p.customer_value
    if model in {EngagementModel.REFERRAL, EngagementModel.DIRECT}:
        beneficiary = request.partner_organization_id
        rate = p.referral_rate if p.referral_rate is not None else Decimal("10")
        has_compensation = (
            p.compensation_rate is not None or p.compensation_beneficiary_id is not None
        )
        if model == EngagementModel.DIRECT and has_compensation:
            if not request.approved:
                raise ValueError("Direct compensation requires an approved term version")
            beneficiary = p.compensation_beneficiary_id
            if beneficiary is None or beneficiary == request.tcg_organization_id:
                raise ValueError("Direct compensation requires an external beneficiary")
            if p.compensation_rate is None:
                raise ValueError("Direct compensation requires an explicit rate")
            rate = p.compensation_rate
        if model == EngagementModel.REFERRAL or has_compensation:
            if p.eligibility is None:
                raise ValueError("An explicit eligible revenue basis is required")
            if p.eligibility.amount > p.customer_value:
                raise ValueError("Eligible revenue cannot exceed customer value")
            commission = money(p.eligibility.amount * rate / HUNDRED)
            result.commission_expense = commission
            result.partner_entitlement = commission
            result.allocations[str(beneficiary)] = commission
        result.allocations[tcg] = money(p.customer_value)
        return result
    if p.pool is None or p.allocation_method is None:
        raise ValueError("SI requires an explicit allocation method and named pool")
    pool = p.pool
    if pool.residual_beneficiary_id not in (
        request.tcg_organization_id,
        request.partner_organization_id,
    ):
        raise ValueError("The residual beneficiary must be a named commercial party")
    if pool.gross_amount > p.customer_value:
        raise ValueError("The pool cannot exceed the customer commercial value")
    deductions = ZERO
    for identifier in pool.deducted_vendor_link_ids:
        if identifier not in costs:
            raise ValueError("An excluded cost must identify a vendor link in this opportunity")
        deductions += costs[identifier].amount
    pool_value = money(pool.gross_amount - deductions)
    if pool_value < 0:
        raise ValueError("Pool deductions exceed the pool")
    result.pool_value = pool_value
    if p.allocation_method == "PERCENT":
        if p.tcg_percentage is None or p.tcg_fixed is not None or p.allocations is not None:
            raise ValueError("Percentage splits require exactly one explicit TCG rate")
        tcg_amount = money(pool_value * p.tcg_percentage / HUNDRED)
        si_amount = money(pool_value * (HUNDRED - p.tcg_percentage) / HUNDRED)
        residual = pool_value - tcg_amount - si_amount
        if pool.residual_beneficiary_id == request.tcg_organization_id:
            tcg_amount += residual
        else:
            si_amount += residual
    elif p.allocation_method == "FIXED":
        if p.tcg_fixed is None or p.tcg_percentage is not None or p.allocations is not None:
            raise ValueError("Fixed allocations require exactly one explicit mcube amount")
        if pool.residual_beneficiary_id != request.partner_organization_id:
            raise ValueError("A fixed mcube allocation requires an explicitly agreed SI residual")
        tcg_amount, si_amount = p.tcg_fixed, pool_value - p.tcg_fixed
        if si_amount < 0:
            raise ValueError("The fixed mcube allocation exceeds the pool")
    else:
        if not p.allocations or p.tcg_fixed is not None or p.tcg_percentage is not None:
            raise ValueError("Itemized terms require explicit component allocations only")
        keys = [a.component_id for a in p.allocations]
        if len(set(keys)) != len(keys) or set(keys) != set(pool.component_ids):
            raise ValueError("Allocate every named component exactly once")
        if any(
            a.beneficiary_id not in (request.tcg_organization_id, request.partner_organization_id)
            for a in p.allocations
        ):
            raise ValueError("Unknown allocation beneficiary")
        if sum((a.amount for a in p.allocations), ZERO) != pool_value:
            raise ValueError("Itemized allocations must reconcile with the pool")
        tcg_amount = sum(
            (a.amount for a in p.allocations if a.beneficiary_id == request.tcg_organization_id),
            ZERO,
        )
        si_amount = pool_value - tcg_amount
    result.tcg_entitlement, result.partner_entitlement = money(tcg_amount), money(si_amount)
    result.allocations = {tcg: money(tcg_amount), partner: money(si_amount)}
    result.si_project_share_percentage = (
        money(si_amount / p.customer_value * HUNDRED) if p.customer_value else ZERO
    )
    if result.si_project_share_percentage <= 50:
        result.warnings.append(
            "SI share is not the major share of the overall project; review required"
        )
    return result


def resolve_parameter_layers(
    layers: list[tuple[int, str, CommercialParameters]],
) -> tuple[CommercialParameters, dict[str, str]]:
    """Equal specificity for any supplied parameter is ambiguous, including explicit zero."""
    selected: dict[str, object] = {}
    sources: dict[str, str] = {}
    ranks: dict[str, int] = {}
    for rank, source, params in sorted(layers, key=lambda row: row[0]):
        for key, value in params.model_dump(exclude_none=True).items():
            if ranks.get(key) == rank:
                raise ValueError(f"Overlapping terms of equal specificity for {key}")
            selected[key], sources[key], ranks[key] = value, source, rank
    return CommercialParameters.model_validate(selected), sources
