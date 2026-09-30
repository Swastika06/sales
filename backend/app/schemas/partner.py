from datetime import datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)

from app.models.partner import PartnerStatus


class MasterDataItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str


class RegistrationOptions(BaseModel):
    partner_types: list[MasterDataItem]
    countries: list[MasterDataItem]
    partner_roles: list[MasterDataItem]


class PartnerRegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company_name: str = Field(min_length=2, max_length=200)
    legal_name: str | None = Field(default=None, max_length=200)
    partner_type_code: str | None = None
    capability_codes: list[str] = Field(default_factory=list, max_length=3)
    country_codes: list[str] = Field(min_length=1, max_length=25)
    website: HttpUrl | None = None
    company_email: EmailStr
    phone: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=2000)
    primary_contact_name: str = Field(min_length=2, max_length=200)
    primary_contact_email: EmailStr
    primary_contact_phone: str | None = Field(default=None, max_length=50)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("partner_type_code")
    @classmethod
    def normalize_partner_type(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else None

    @model_validator(mode="after")
    def normalize_capabilities(self) -> "PartnerRegistrationRequest":
        codes = self.capability_codes or (
            [self.partner_type_code] if self.partner_type_code else []
        )
        self.capability_codes = list(dict.fromkeys(code.strip().upper() for code in codes))
        allowed = {"RESELLER", "REFERRAL", "SYSTEM_INTEGRATOR"}
        if not self.capability_codes or not set(self.capability_codes) <= allowed:
            raise ValueError("Select one or more valid partner capabilities")
        self.partner_type_code = self.capability_codes[0]
        return self

    @field_validator("country_codes")
    @classmethod
    def normalize_country_codes(cls, values: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(value.strip().upper() for value in values))
        if any(len(value) != 2 for value in normalized):
            raise ValueError("Country codes must be ISO 3166-1 alpha-2 values")
        return normalized


class AdminPartnerCreate(PartnerRegistrationRequest):
    organization_id: UUID | None = None


class PartnerUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company_name: str | None = Field(default=None, min_length=2, max_length=200)
    legal_name: str | None = Field(default=None, max_length=200)
    partner_type_code: str | None = None
    capability_codes: list[str] | None = Field(default=None, min_length=1, max_length=3)
    country_codes: list[str] | None = Field(default=None, min_length=1, max_length=25)
    website: HttpUrl | None = None
    company_email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=2000)
    primary_contact_name: str | None = Field(default=None, min_length=2, max_length=200)
    primary_contact_email: EmailStr | None = None
    primary_contact_phone: str | None = Field(default=None, max_length=50)

    @field_validator("partner_type_code")
    @classmethod
    def normalize_optional_code(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else value

    @field_validator("country_codes")
    @classmethod
    def normalize_optional_countries(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        normalized = list(dict.fromkeys(value.strip().upper() for value in values))
        if any(len(value) != 2 for value in normalized):
            raise ValueError("Country codes must be ISO 3166-1 alpha-2 values")
        return normalized


class PartnerDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PartnerRejectionRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class PartnerStatusUpdate(BaseModel):
    status: PartnerStatus


class PartnerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str | None
    company_name: str
    legal_name: str | None
    company_email: EmailStr
    website: str | None
    phone: str | None
    address: str | None
    primary_contact_name: str
    primary_contact_email: EmailStr
    primary_contact_phone: str | None
    status: PartnerStatus
    rejection_reason: str | None
    approved_at: datetime | None
    partner_type: MasterDataItem
    capabilities: list[MasterDataItem]
    organization_id: UUID | None
    countries: list[MasterDataItem]
    created_at: datetime
    updated_at: datetime


class PartnerListResponse(BaseModel):
    items: list[PartnerRead]
    total: int
    page: int
    page_size: int


class PartnerUserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=200)
    password: str = Field(min_length=12, max_length=128)
    role_codes: list[str] = Field(min_length=1, max_length=4)

    @field_validator("role_codes")
    @classmethod
    def normalize_roles(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip().upper() for value in values))


class PartnerUserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    is_active: bool | None = None
    role_codes: list[str] | None = Field(default=None, min_length=1, max_length=4)

    @field_validator("role_codes")
    @classmethod
    def normalize_roles(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        return list(dict.fromkeys(value.strip().upper() for value in values))


class PartnerUserRead(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str
    is_active: bool
    roles: list[str]
    created_at: datetime
