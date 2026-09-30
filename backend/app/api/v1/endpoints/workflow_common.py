from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.access import is_tcg_user, role_codes
from app.models.identity import User
from app.models.sales import StoredAttachment
from app.storage.client import put_private_object

MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def actor_role(user: User) -> str | None:
    return sorted(role_codes(user))[0] if user.roles else None


def require_partner_scope(user: User, partner_id: UUID | None) -> None:
    if not is_tcg_user(user) and (
        partner_id is None or user.partner_id is None or user.partner_id != partner_id
    ):
        raise HTTPException(status_code=403, detail="This record belongs to another partner")


def require_tcg(user: User) -> None:
    if not is_tcg_user(user):
        raise HTTPException(status_code=403, detail="TCG access is required")


def require_sales_manage(user: User) -> None:
    if user.is_superuser:
        return
    granted = {permission.code for role in user.roles for permission in role.permissions}
    if "sales.manage" not in granted:
        raise HTTPException(status_code=403, detail="Sales management permission is required")


def choose_partner_id(user: User, requested: UUID | None) -> UUID:
    if is_tcg_user(user):
        if requested is None:
            raise HTTPException(status_code=422, detail="partner_id is required for TCG users")
        return requested
    if user.partner_id is None:
        raise HTTPException(status_code=403, detail="A partner account is required")
    if requested is not None and requested != user.partner_id:
        raise HTTPException(status_code=403, detail="Cannot create records for another partner")
    return user.partner_id


def make_reference(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:10].upper()}"


async def store_attachment(
    session: AsyncSession,
    *,
    owner_type: str,
    owner_id: UUID,
    kind: str,
    file: UploadFile,
    user: User,
) -> StoredAttachment:
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(status_code=422, detail="The uploaded file is empty")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Files are limited to 25 MB")
    safe_name = Path(file.filename or "attachment.bin").name
    object_key = f"{owner_type.lower()}/{owner_id}/{uuid4().hex}-{safe_name}"
    content_type = file.content_type or "application/octet-stream"
    put_private_object(object_key, data, content_type)
    attachment = StoredAttachment(
        owner_type=owner_type,
        owner_id=owner_id,
        kind=kind,
        object_key=object_key,
        file_name=safe_name,
        content_type=content_type,
        size_bytes=len(data),
        checksum_sha256=sha256(data).hexdigest(),
        uploaded_by_id=user.id,
    )
    session.add(attachment)
    return attachment
