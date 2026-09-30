"""Acceptance fixtures from Commercial-Model.md; amounts are not catalog defaults."""

from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.commercial import calculate_commercial, resolve_parameter_layers
from app.schemas.commercial import CalculationRequest, CommercialParameters
from app.schemas.pricing import ProductCreate

TCG, PARTNER, COMPONENT, VENDOR, CUSTOMER = [uuid4() for _ in range(5)]


def eligibility(amount="80000"):
    return dict(
        component_ids=[COMPONENT],
        amount=amount,
        discounts="Net of discounts",
        taxes="Excluded",
        vendor_charges="Excluded",
        credits="Deduct agreed credits",
        refunds="Adjust under agreed policy",
    )


def calculate(model, vendor_costs=None, approved=False, **parameters):
    return calculate_commercial(
        CalculationRequest.model_validate(
            dict(
                engagement_model=model,
                tcg_organization_id=TCG,
                partner_organization_id=None if model == "DIRECT" else PARTNER,
                parameters=parameters,
                vendor_costs=vendor_costs or [],
                approved=approved,
            )
        )
    )


def pool(amount="200000", **kwargs):
    return dict(
        name="Agreed whole-project services",
        component_ids=[COMPONENT],
        gross_amount=amount,
        residual_beneficiary_id=PARTNER,
        **kwargs,
    )


@pytest.mark.parametrize(
    "selling,margin", [("100000", Decimal("20000")), (None, None), ("70000", Decimal("-10000"))]
)
def test_reseller_wholesale_independent_of_customer_price(selling, margin):
    result = calculate("RESELLER", wholesale_value="80000", customer_selling_value=selling)
    assert result.tcg_entitlement == 80000
    assert result.reseller_gross_margin == margin
    assert result.customer_value == (Decimal(selling) if selling else None)
    assert result.commission_expense == 0


@pytest.mark.parametrize(
    "rate,expected", [(None, "8000"), ("12", "9600"), ("0", "0"), ("100", "80000")]
)
def test_referral_rate_and_separate_customer_invoice(rate, expected):
    result = calculate(
        "REFERRAL", customer_value="100000", eligibility=eligibility(), referral_rate=rate
    )
    assert result.partner_entitlement == Decimal(expected)
    assert result.commission_expense == Decimal(expected)
    assert result.customer_value == result.tcg_entitlement == 100000


@pytest.mark.parametrize("rate", ["-0.1", "100.1"])
def test_invalid_rate(rate):
    with pytest.raises(ValidationError):
        CommercialParameters(referral_rate=Decimal(rate))


def test_referral_missing_basis_is_blocked():
    with pytest.raises(ValueError, match="eligible revenue"):
        calculate("REFERRAL", customer_value="100000")


def test_reseller_cannot_receive_referral_commission():
    with pytest.raises(ValueError, match="Referral allocations"):
        calculate("RESELLER", wholesale_value="80000", referral_rate="10")


def test_si_percentage_split():
    result = calculate(
        "SYSTEM_INTEGRATOR",
        customer_value="200000",
        pool=pool(),
        allocation_method="PERCENT",
        tcg_percentage="30",
    )
    assert (result.tcg_entitlement, result.partner_entitlement) == (60000, 140000)
    assert result.si_project_share_percentage == 70
    assert not result.warnings


def test_si_fixed_allocation():
    result = calculate(
        "SYSTEM_INTEGRATOR",
        customer_value="200000",
        pool=pool(),
        allocation_method="FIXED",
        tcg_fixed="50000",
    )
    assert (result.tcg_entitlement, result.partner_entitlement) == (50000, 150000)


def test_si_no_implicit_share_or_markup():
    with pytest.raises(ValueError, match="explicit allocation"):
        calculate("SYSTEM_INTEGRATOR", customer_value="200000")


def test_si_named_residual_reconciles_half_cent():
    result = calculate(
        "SYSTEM_INTEGRATOR",
        customer_value="0.01",
        pool=pool("0.01"),
        allocation_method="PERCENT",
        tcg_percentage="50",
    )
    assert result.tcg_entitlement == Decimal("0.01")
    assert result.partner_entitlement == 0
    assert sum(result.allocations.values()) == Decimal("0.01")
    assert result.warnings


def test_si_major_share_uses_overall_project_not_pool():
    result = calculate(
        "SYSTEM_INTEGRATOR",
        customer_value="200000",
        pool=pool("100000"),
        allocation_method="PERCENT",
        tcg_percentage="30",
    )
    assert result.si_project_share_percentage == 35
    assert result.warnings


def test_vendor_obligation_does_not_reduce_direct_customer_value():
    result = calculate(
        "DIRECT",
        customer_value="100000",
        vendor_costs=[dict(link_id=VENDOR, payer_id=TCG, amount="10000")],
    )
    assert result.tcg_entitlement == result.customer_value == 100000
    assert result.vendor_cost == 10000
    assert result.partner_entitlement == result.commission_expense == 0
    assert str(VENDOR) not in result.allocations


def test_direct_exception_requires_approved_explicit_beneficiary():
    params = dict(
        customer_value="100000",
        compensation_beneficiary_id=PARTNER,
        compensation_rate="5",
        eligibility=eligibility("40000"),
    )
    with pytest.raises(ValueError, match="approved"):
        calculate("DIRECT", **params)
    result = calculate("DIRECT", approved=True, **params)
    assert result.commission_expense == result.partner_entitlement == 2000
    assert result.tcg_entitlement == 100000


def test_vendor_deduction_applied_once():
    result = calculate(
        "SYSTEM_INTEGRATOR",
        customer_value="200000",
        pool=pool(deducted_vendor_link_ids=[VENDOR]),
        allocation_method="PERCENT",
        tcg_percentage="30",
        vendor_costs=[dict(link_id=VENDOR, payer_id=TCG, amount="10000")],
    )
    assert result.pool_value == 190000
    assert sum(result.allocations.values()) == 190000
    assert result.vendor_cost == 10000
    assert result.tcg_entitlement == 57000


def test_customer_paid_vendor_is_separate_unless_explicitly_in_pool():
    cost = [dict(link_id=VENDOR, payer_id=CUSTOMER, amount="10000")]
    result = calculate(
        "SYSTEM_INTEGRATOR",
        customer_value="200000",
        pool=pool(),
        allocation_method="PERCENT",
        tcg_percentage="30",
        vendor_costs=cost,
    )
    assert result.pool_value == 200000
    explicit = calculate(
        "SYSTEM_INTEGRATOR",
        customer_value="200000",
        pool=pool(deducted_vendor_link_ids=[VENDOR]),
        allocation_method="PERCENT",
        tcg_percentage="30",
        vendor_costs=cost,
    )
    assert explicit.pool_value == 190000


def test_duplicate_vendor_deduction_rejected():
    with pytest.raises(ValidationError, match="deducted twice"):
        calculate(
            "SYSTEM_INTEGRATOR",
            customer_value="200000",
            pool=pool(deducted_vendor_link_ids=[VENDOR, VENDOR]),
        )


def test_itemized_scope_and_totals():
    component2 = uuid4()
    scoped_pool = pool()
    scoped_pool["component_ids"] = [COMPONENT, component2]
    allocations = [
        dict(component_id=COMPONENT, beneficiary_id=TCG, amount="50000"),
        dict(component_id=component2, beneficiary_id=PARTNER, amount="150000"),
    ]
    result = calculate(
        "SYSTEM_INTEGRATOR",
        customer_value="200000",
        pool=scoped_pool,
        allocation_method="ITEMIZED",
        allocations=allocations,
    )
    assert result.tcg_entitlement == 50000
    allocations[1]["amount"] = "100000"
    with pytest.raises(ValueError, match="reconcile"):
        calculate(
            "SYSTEM_INTEGRATOR",
            customer_value="200000",
            pool=scoped_pool,
            allocation_method="ITEMIZED",
            allocations=allocations,
        )


def test_explicit_zero_overrides_default_and_sources_preserved():
    resolved, sources = resolve_parameter_layers(
        [
            (2, "default", CommercialParameters(referral_rate=Decimal("10"))),
            (6, "opportunity", CommercialParameters(referral_rate=Decimal("12"))),
            (8, "contract", CommercialParameters(referral_rate=Decimal("0"))),
        ]
    )
    assert resolved.referral_rate == 0
    assert sources["referral_rate"] == "contract"


def test_equal_priority_terms_rejected():
    with pytest.raises(ValueError, match="Overlapping"):
        resolve_parameter_layers(
            [
                (2, "a", CommercialParameters(discount_percentage=Decimal("5"))),
                (2, "b", CommercialParameters(discount_percentage=Decimal("0"))),
            ]
        )


def test_product_codes_are_normalized_by_contract():
    with pytest.raises(ValidationError):
        ProductCreate(code="lowercase", name="Example")
