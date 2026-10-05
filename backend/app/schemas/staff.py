from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.auth import UserRead

STAFF_ROLES = {
    "TCG_ADMIN": "Admin",
    "TCG_FINANCE": "Finance",
    "TCG_SALES": "Sales",
    "TCG_LEGAL": "Legal",
}


class StaffUserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    role_code: Literal["TCG_ADMIN", "TCG_FINANCE", "TCG_SALES", "TCG_LEGAL"]

    @field_validator("full_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Enter a full name of at least two characters")
        return value


class StaffUserRead(UserRead):
    created_at: datetime
    mail_status: str | None = None
