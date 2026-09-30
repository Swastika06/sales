from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version_number: int
    file_name: str
    content_type: str
    size_bytes: int
    checksum_sha256: str
    change_note: str | None
    created_at: datetime


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None
    category: str
    visibility: str
    product_id: UUID | None
    partner_type_id: UUID | None
    partner_id: UUID | None
    is_active: bool
    versions: list[DocumentVersionRead]
    created_at: datetime
    updated_at: datetime


class DownloadRead(BaseModel):
    url: str
    expires_in_seconds: int = 600
