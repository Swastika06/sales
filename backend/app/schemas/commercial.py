from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

Amount = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2)]
Rate = Annotated[Decimal, Field(ge=0, le=100, max_digits=9, decimal_places=6)]


class EngagementModel(StrEnum):
    DIRECT = "DIRECT"
    RESELLER = "RESELLER"
    REFERRAL = "REFERRAL"
    SYSTEM_INTEGRATOR = "SYSTEM_INTEGRATOR"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Eligibility(StrictModel):
    component_ids: list[UUID] = Field(min_length=1)
    amount: Amount
    discounts: str = Field(min_length=1, max_length=1000)
    taxes: str = Field(min_length=1, max_length=1000)
    vendor_charges: str = Field(min_length=1, max_length=1000)
    credits: str = Field(min_length=1, max_length=1000)
    refunds: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def explicit_scope(self) -> "Eligibility":
        if len(set(self.component_ids)) != len(self.component_ids):
            raise ValueError("Eligible components must be unique")
        for value in (self.discounts, self.taxes, self.vendor_charges, self.credits, self.refunds):
            if not value.strip():
                raise ValueError("Every eligibility treatment must be explicitly described")
        return self


class AllocationLine(StrictModel):
    component_id: UUID
    beneficiary_id: UUID
    amount: Amount


class VendorCost(StrictModel):
    link_id: UUID
    payer_id: UUID
    amount: Amount


class Pool(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    component_ids: list[UUID] = Field(min_length=1)
    gross_amount: Amount
    deducted_vendor_link_ids: list[UUID] = Field(default_factory=list)
    residual_beneficiary_id: UUID

    @model_validator(mode="after")
    def unique_scope(self) -> "Pool":
        if len(set(self.component_ids)) != len(self.component_ids):
            raise ValueError("Pool components cannot be counted twice")
        if len(set(self.deducted_vendor_link_ids)) != len(self.deducted_vendor_link_ids):
            raise ValueError("A vendor cost cannot be deducted twice")
        return self


class CommercialParameters(StrictModel):
    fixed_unit_price: Amount | None = None
    discount_percentage: Rate | None = None
    referral_rate: Rate | None = None
    customer_value: Amount | None = None
    customer_selling_value: Amount | None = None
    wholesale_value: Amount | None = None
    eligibility: Eligibility | None = None
    allocation_method: Literal["FIXED", "PERCENT", "ITEMIZED"] | None = None
    pool: Pool | None = None
    tcg_percentage: Rate | None = None
    tcg_fixed: Amount | None = None
    allocations: list[AllocationLine] | None = None
    compensation_beneficiary_id: UUID | None = None
    compensation_rate: Rate | None = None
    settlement_policy: str | None = Field(default=None, max_length=4000)


class CalculationRequest(StrictModel):
    engagement_model: EngagementModel
    tcg_organization_id: UUID
    partner_organization_id: UUID | None = None
    parameters: CommercialParameters
    vendor_costs: list[VendorCost] = Field(default_factory=list)
    approved: bool = False


class CalculationResult(StrictModel):
    currency: Literal["USD"] = "USD"
    customer_value: Decimal | None
    tcg_entitlement: Decimal
    partner_entitlement: Decimal | None
    vendor_cost: Decimal
    commission_expense: Decimal
    reseller_gross_margin: Decimal | None = None
    pool_value: Decimal | None = None
    si_project_share_percentage: Decimal | None = None
    allocations: dict[str, Decimal]
    vendor_costs_by_payer: dict[str, Decimal]
    warnings: list[str] = Field(default_factory=list)


class ParticipantInput(StrictModel):
    organization_id: UUID
    capability: Literal["RESELLER", "REFERRAL", "SYSTEM_INTEGRATOR"] | None = None
    access_level: Literal["NONE", "PROGRESS", "COMMERCIAL"] = "NONE"
    active: bool = True


class RoleInput(StrictModel):
    organization_id: UUID
    role: Literal[
        "CUSTOMER_RELATIONSHIP_OWNER",
        "BIDDER",
        "CONTRACTING_SELLER",
        "MCUBE_SELLER",
        "DELIVERY_LEAD",
        "REFERRER",
        "PRODUCT_OWNER",
        "TECHNOLOGY_PROVIDER",
        "BILL_TO",
    ]
    scope: str = Field(default="OPPORTUNITY", min_length=1, max_length=100)
    primary: bool = True


class ComponentInput(StrictModel):
    id: UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    product_id: UUID | None = None
    sku_id: UUID | None = None
    external_service: str | None = Field(default=None, max_length=200)
    owner_organization_id: UUID
    seller_organization_id: UUID
    delivery_organization_id: UUID
    billing_organization_id: UUID
    amount: Amount = Decimal("0")

    @model_validator(mode="after")
    def product_or_service(self) -> "ComponentInput":
        if self.product_id is None and not self.external_service:
            raise ValueError("A product or external service is required")
        return self


class EngagementUpdate(StrictModel):
    expected_version: int = Field(ge=0)
    engagement_model: EngagementModel
    partner_id: UUID | None = None
    responsible_user_id: UUID | None = None
    participants: list[ParticipantInput]
    roles: list[RoleInput]
    components: list[ComponentInput]
    amendment_reason: str | None = Field(default=None, min_length=3, max_length=1000)


class TermCreate(StrictModel):
    expected_version: int = Field(ge=0)
    engagement_model: EngagementModel
    scope: Literal["DEFAULT", "PARTNER", "OPPORTUNITY", "CONTRACT"]
    partner_agreement_id: UUID | None = None
    opportunity_id: UUID | None = None
    contract_id: UUID | None = None
    sku_id: UUID | None = None
    effective_from: date
    effective_until: date | None = None
    supersedes_id: UUID | None = None
    parameters: CommercialParameters

    @model_validator(mode="after")
    def scope_matches(self) -> "TermCreate":
        ids = {
            "PARTNER": self.partner_agreement_id,
            "OPPORTUNITY": self.opportunity_id,
            "CONTRACT": self.contract_id,
        }
        for scope, identifier in ids.items():
            if (scope == self.scope) != (identifier is not None):
                raise ValueError("Provide exactly the identifier matching the term scope")
        if self.effective_until and self.effective_until < self.effective_from:
            raise ValueError("Invalid term date range")
        return self


class OrganizationCreate(StrictModel):
    legal_name: str = Field(min_length=2, max_length=200)
    identifier: str = Field(min_length=2, max_length=200)


class VendorProfileCreate(StrictModel):
    organization_id: UUID
    category: str = Field(min_length=2, max_length=100)
    commercial_contact: str = Field(min_length=2, max_length=320)


class PartnerAgreementCreate(StrictModel):
    partner_id: UUID
    engagement_model: EngagementModel
    effective_from: date
    effective_until: date | None = None
    document_id: UUID | None = None


class VendorAgreementCreate(StrictModel):
    provider_organization_id: UUID
    buyer_organization_id: UUID
    billing_basis: str = Field(min_length=2, max_length=2000)
    charge_model: Literal["LICENSE", "USAGE", "INFRASTRUCTURE", "SERVICE"]
    effective_from: date
    effective_until: date | None = None
    document_id: UUID | None = None
    secret_reference: str | None = Field(default=None, pattern=r"^secret://[a-zA-Z0-9/_.-]+$")


class VendorLinkCreate(StrictModel):
    expected_version: int = Field(ge=0)
    agreement_id: UUID
    component_id: UUID | None = None
    payer_organization_id: UUID
    usage_responsibility: str = Field(min_length=2, max_length=1000)
    amount: Amount
    cost_treatment: Literal["SEPARATE", "POOL_DEDUCTION"] = "SEPARATE"


class ContractCreate(StrictModel):
    expected_version: int = Field(ge=0)
    opportunity_id: UUID
    seller_organization_id: UUID
    buyer_organization_id: UUID
    kind: Literal["CUSTOMER", "WHOLESALE", "PROJECT"]
    document_id: UUID | None = None


class ConversionCreate(StrictModel):
    expected_version: int = Field(ge=0)
    evidence: str = Field(min_length=3, max_length=2000)
    actual_eligibility: Eligibility | None = None
    snapshot_id: UUID


class AccrualAdjustmentCreate(StrictModel):
    event_key: str = Field(min_length=3, max_length=200)
    amount: Decimal = Field(max_digits=18, decimal_places=2)
    reason: str = Field(min_length=3, max_length=2000)


class SettlementCreate(StrictModel):
    expected_version: int = Field(ge=0)
    payment_reference: str = Field(min_length=3, max_length=200)
    amount: Amount
