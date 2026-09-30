from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.pricing import SkuCategory


class EffectiveDatedSchema(BaseModel):
    effective_from: date
    effective_until: date | None = None

    @model_validator(mode="after")
    def validate_date_range(self) -> "EffectiveDatedSchema":
        if self.effective_until and self.effective_until < self.effective_from:
            raise ValueError("effective_until must be on or after effective_from")
        return self


class ProductCreate(BaseModel):
    owner_organization_id: UUID | None = None
    code: str = Field(min_length=2, max_length=50, pattern=r"^[A-Z0-9][A-Z0-9_-]*$")
    name: str = Field(min_length=2, max_length=150)
    description: str | None = Field(default=None, max_length=4000)


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    description: str | None = Field(default=None, max_length=4000)
    is_active: bool | None = None


class SkuCreate(BaseModel):
    code: str = Field(min_length=2, max_length=80, pattern=r"^[A-Z0-9][A-Z0-9_-]*$")
    name: str = Field(min_length=2, max_length=150)
    description: str | None = Field(default=None, max_length=4000)
    category: SkuCategory
    unit: str = Field(default="unit", min_length=1, max_length=50)


class SkuUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    description: str | None = Field(default=None, max_length=4000)
    category: SkuCategory | None = None
    unit: str | None = Field(default=None, min_length=1, max_length=50)
    is_active: bool | None = None


class SkuRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    code: str
    name: str
    description: str | None
    category: SkuCategory
    unit: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProductRead(BaseModel):
    owner_organization_id: UUID | None
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    description: str | None
    is_active: bool
    skus: list[SkuRead]
    created_at: datetime
    updated_at: datetime


class ProductPriceCreate(EffectiveDatedSchema):
    amount: Decimal = Field(ge=0, max_digits=18, decimal_places=2)


class ProductPriceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sku_id: UUID
    amount: Decimal
    currency: str
    effective_from: date
    effective_until: date | None
    is_active: bool


class PriceBreakdown(BaseModel):
    list_price: Decimal | None = None
    sources: dict[str, str]


class ResolvedPriceRead(BaseModel):
    product_id: UUID
    product_code: str
    product_name: str
    sku_id: UUID
    sku_code: str
    sku_name: str
    sku_description: str | None
    unit: str
    currency: str = "USD"
    final_price: Decimal
    effective_from: date
    effective_until: date | None = None
    commercial_model: str
    commission_percentage: Decimal | None = None
    breakdown: PriceBreakdown | None = None


class PartnerPricingResponse(BaseModel):
    partner_id: UUID | None
    partner_name: str
    as_of: date
    currency: str = "USD"
    items: list[ResolvedPriceRead]
