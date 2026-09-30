from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class ApplicationAccess(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class LegalAssignment(BaseModel):
    reviewer_id: UUID


class LegalDecision(BaseModel):
    decision: Literal["APPROVE", "REQUEST_CHANGES", "REJECT"]
    revision: int = Field(ge=1)
    comment: str = Field(default="", max_length=2000)


class ActivationCode(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


class LegalReviewerCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=200)
    password: str = Field(min_length=12, max_length=128)
