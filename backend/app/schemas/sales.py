from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.commercial import EngagementModel


class CustomerCreate(BaseModel):
    organization_id: UUID | None = None
    name: str = Field(min_length=2, max_length=200)
    legal_name: str | None = Field(default=None, max_length=200)
    website: str | None = Field(default=None, max_length=500)
    industry: str | None = Field(default=None, max_length=100)
    country_code: str = Field(min_length=2, max_length=2)
    contact_name: str | None = Field(default=None, max_length=200)
    contact_email: str | None = Field(default=None, max_length=320)


class CustomerRead(CustomerCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime


class DealCreate(BaseModel):
    engagement_model: EngagementModel
    partner_id: UUID | None = None
    customer_id: UUID | None = None
    customer: CustomerCreate | None = None
    product_id: UUID
    name: str = Field(min_length=2, max_length=200)
    description: str | None = None
    estimated_value: Decimal = Field(default=Decimal("0"), ge=0)
    expected_close_date: date | None = None


class DealStageChange(BaseModel):
    stage: str
    note: str | None = Field(default=None, max_length=1000)
    actual_contract_value: Decimal | None = Field(default=None, ge=0)
    actual_close_date: date | None = None
    lost_reason: str | None = Field(default=None, max_length=1000)


class ReasonBody(BaseModel):
    reason: str = Field(min_length=2, max_length=1000)


class StageHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    from_stage: str | None
    to_stage: str
    note: str | None
    changed_at: datetime


class DealRead(BaseModel):
    engagement_model: EngagementModel | None
    commercial_version: int
    migration_review_required: bool
    responsible_user_id: UUID | None
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    reference: str
    partner_id: UUID | None
    customer_id: UUID
    product_id: UUID
    name: str
    description: str | None
    estimated_value: Decimal
    currency: str
    expected_close_date: date | None
    approval_status: str
    stage: str
    review_reason: str | None
    protection_expires_at: datetime | None
    actual_contract_value: Decimal | None
    actual_close_date: date | None
    lost_reason: str | None
    customer: CustomerRead
    stage_history: list[StageHistoryRead]
    created_at: datetime
    updated_at: datetime


class QuoteCreate(BaseModel):
    opportunity_id: UUID
    commercial_model: EngagementModel | None = None
    contract_id: UUID | None = None
    valid_until: date | None = None
    notes: str | None = None


class QuoteItemCreate(BaseModel):
    sku_id: UUID
    quantity: Decimal = Field(gt=0)
    discount_percentage: Decimal = Field(default=Decimal("0"), ge=0, le=100)


class QuoteItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    sku_id: UUID
    sku_code: str
    sku_name: str
    quantity: Decimal
    unit_price: Decimal
    discount_percentage: Decimal
    line_total: Decimal
    pricing_snapshot: dict[str, object]


class QuoteRead(BaseModel):
    contract_id: UUID | None
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    reference: str
    opportunity_id: UUID
    partner_id: UUID | None
    status: str
    commercial_model: str
    valid_until: date | None
    currency: str
    subtotal: Decimal
    discount_total: Decimal
    total: Decimal
    current_revision: int
    notes: str | None
    items: list[QuoteItemRead]
    created_at: datetime
    updated_at: datetime


class StatusChange(BaseModel):
    status: str
    reason: str | None = Field(default=None, max_length=1000)


class MafCreate(BaseModel):
    partner_id: UUID | None = None
    opportunity_id: UUID
    tender_reference: str = Field(min_length=2, max_length=150)
    tender_authority: str = Field(min_length=2, max_length=200)
    tender_due_date: date
    tender_value: Decimal | None = Field(default=None, ge=0)
    details: str | None = None


class MafRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    reference: str
    opportunity_id: UUID
    partner_id: UUID | None
    status: str
    tender_reference: str
    tender_authority: str
    tender_due_date: date
    tender_value: Decimal | None
    details: str | None
    review_reason: str | None
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime


class OrderCreate(BaseModel):
    quote_id: UUID
    billing_name: str = Field(min_length=2, max_length=200)
    billing_address: str = Field(min_length=4)
    billing_email: str = Field(min_length=3, max_length=320)


class OrderHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    from_status: str | None
    to_status: str
    note: str | None
    changed_at: datetime


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    reference: str
    quote_id: UUID
    partner_id: UUID | None
    status: str
    billing_name: str
    billing_address: str
    billing_email: str
    currency: str
    total: Decimal
    review_reason: str | None
    confirmed_at: datetime | None
    status_history: list[OrderHistoryRead]
    created_at: datetime
    updated_at: datetime


class AttachmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    owner_type: str
    owner_id: UUID
    kind: str
    file_name: str
    content_type: str
    size_bytes: int
    created_at: datetime
