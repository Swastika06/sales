from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    full_name: str
    must_change_password: bool = False
    is_active: bool
    is_superuser: bool
    partner_id: UUID | None
    roles: list[str]
    permissions: list[str]
