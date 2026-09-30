from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.elements import ColumnElement

from app.api.dependencies import get_current_user
from app.api.v1.endpoints.workflow_common import MAX_UPLOAD_BYTES
from app.db.session import get_db
from app.domain.access import is_tcg_admin, is_tcg_user
from app.domain.documents import can_access_document
from app.models.commercial import CommercialContract, VendorAgreement
from app.models.content import Document, DocumentCategory, DocumentVersion, DocumentVisibility
from app.models.identity import User
from app.models.partner import Partner
from app.schemas.content import DocumentRead, DownloadRead
from app.services.audit import record_audit_event
from app.services.commercial_access import visible_contract_ids
from app.storage.client import presigned_download_url, put_private_object

router = APIRouter()


def require_admin(user: User) -> None:
    if not is_tcg_admin(user):
        raise HTTPException(status_code=403, detail="TCG Admin access is required")


async def get_document(session: AsyncSession, document_id: UUID) -> Document:
    document = await session.scalar(
        select(Document).where(Document.id == document_id).options(selectinload(Document.versions))
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


async def partner_context(session: AsyncSession, user: User) -> Partner | None:
    if user.partner_id is None:
        return None
    return await session.get(Partner, user.partner_id)


def commercial_document_scope(user: User) -> tuple[ColumnElement[bool], ColumnElement[bool]]:
    vendor_docs = select(VendorAgreement.document_id).where(
        VendorAgreement.document_id.is_not(None)
    )
    unshared_contract_docs = select(CommercialContract.document_id).where(
        CommercialContract.document_id.is_not(None),
        CommercialContract.id.not_in(visible_contract_ids(user)),
    )
    return ~Document.id.in_(vendor_docs), ~Document.id.in_(unshared_contract_docs)


async def require_document_access(session: AsyncSession, user: User, document: Document) -> None:
    partner = await partner_context(session, user)
    if not is_tcg_user(user) and not await session.scalar(
        select(Document.id).where(Document.id == document.id, *commercial_document_scope(user))
    ):
        raise HTTPException(404, "Document not found")
    if not document.is_active:
        raise HTTPException(404, "Document not found")
    if not can_access_document(
        visibility=document.visibility,
        is_tcg=is_tcg_user(user),
        user_partner_id=user.partner_id,
        user_partner_type_id=partner.partner_type_id if partner else None,
        user_partner_tier_id=None,
        user_capability_ids={c.id for c in partner.capabilities} if partner else set(),
        document_partner_id=document.partner_id,
        document_partner_type_id=document.partner_type_id,
        document_partner_tier_id=document.partner_tier_id,
    ):
        raise HTTPException(status_code=404, detail="Document not found")


def validate_scope(
    visibility: str,
    partner_id: UUID | None,
    partner_type_id: UUID | None,
    partner_tier_id: UUID | None,
) -> None:
    missing_scope = (visibility == DocumentVisibility.SPECIFIC_PARTNER and partner_id is None) or (
        visibility == DocumentVisibility.PARTNER_TYPE and partner_type_id is None
    )
    if missing_scope:
        raise HTTPException(status_code=422, detail=f"A scope id is required for {visibility}")


async def save_version(
    session: AsyncSession,
    *,
    document: Document,
    file: UploadFile,
    version_number: int,
    user: User,
    change_note: str | None,
) -> DocumentVersion:
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(status_code=422, detail="The uploaded file is empty")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Files are limited to 25 MB")
    safe_name = Path(file.filename or "document.bin").name
    key = f"documents/{document.id}/v{version_number}/{uuid4().hex}-{safe_name}"
    content_type = file.content_type or "application/octet-stream"
    put_private_object(key, data, content_type)
    version = DocumentVersion(
        document_id=document.id,
        version_number=version_number,
        object_key=key,
        file_name=safe_name,
        content_type=content_type,
        size_bytes=len(data),
        checksum_sha256=sha256(data).hexdigest(),
        change_note=change_note,
        uploaded_by_id=user.id,
    )
    session.add(version)
    return version


@router.get("", response_model=list[DocumentRead])
async def list_documents(
    search: str | None = None,
    category: str | None = None,
    product_id: UUID | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[DocumentRead]:
    statement = (
        select(Document)
        .where(Document.is_active.is_(True))
        .options(selectinload(Document.versions))
        .order_by(Document.updated_at.desc())
    )
    if not is_tcg_user(user):
        statement = statement.where(*commercial_document_scope(user))
    if search:
        term = f"%{search.strip()}%"
        statement = statement.where(
            or_(Document.title.ilike(term), Document.description.ilike(term))
        )
    if category:
        statement = statement.where(Document.category == category)
    if product_id:
        statement = statement.where(Document.product_id == product_id)
    partner = await partner_context(session, user)
    documents = list(await session.scalars(statement))
    visible = [
        document
        for document in documents
        if can_access_document(
            visibility=document.visibility,
            is_tcg=is_tcg_user(user),
            user_partner_id=user.partner_id,
            user_partner_type_id=partner.partner_type_id if partner else None,
            user_partner_tier_id=None,
            user_capability_ids={c.id for c in partner.capabilities} if partner else set(),
            document_partner_id=document.partner_id,
            document_partner_type_id=document.partner_type_id,
            document_partner_tier_id=document.partner_tier_id,
        )
    ]
    return [DocumentRead.model_validate(document) for document in visible]


@router.post("", response_model=DocumentRead, status_code=201)
async def create_document(
    request: Request,
    title: str = Form(...),
    category: str = Form(...),
    visibility: str = Form(...),
    description: str | None = Form(None),
    product_id: UUID | None = Form(None),
    partner_type_id: UUID | None = Form(None),
    partner_id: UUID | None = Form(None),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> DocumentRead:
    require_admin(user)
    if category not in DocumentCategory or visibility not in DocumentVisibility:
        raise HTTPException(status_code=422, detail="Invalid document category or visibility")
    validate_scope(visibility, partner_id, partner_type_id, None)
    document = Document(
        title=title.strip(),
        description=description,
        category=category,
        visibility=visibility,
        product_id=product_id,
        partner_type_id=partner_type_id,
        partner_id=partner_id,
        created_by_id=user.id,
    )
    session.add(document)
    await session.flush()
    await save_version(
        session,
        document=document,
        file=file,
        version_number=1,
        user=user,
        change_note="Initial version",
    )
    await record_audit_event(
        session,
        action="document.published",
        entity_type="document",
        entity_id=str(document.id),
        actor_user_id=user.id,
        new_values={"visibility": visibility, "category": category, "version": 1},
        request_id=getattr(request.state, "request_id", None),
    )
    await session.commit()
    return DocumentRead.model_validate(await get_document(session, document.id))


@router.post("/{document_id}/versions", response_model=DocumentRead, status_code=201)
async def add_document_version(
    document_id: UUID,
    request: Request,
    file: UploadFile = File(...),
    change_note: str | None = Form(None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> DocumentRead:
    require_admin(user)
    document = await get_document(session, document_id)
    next_version = max((version.version_number for version in document.versions), default=0) + 1
    await save_version(
        session,
        document=document,
        file=file,
        version_number=next_version,
        user=user,
        change_note=change_note,
    )
    await record_audit_event(
        session,
        action="document.version_added",
        entity_type="document",
        entity_id=str(document.id),
        actor_user_id=user.id,
        new_values={"version": next_version},
        request_id=getattr(request.state, "request_id", None),
    )
    await session.commit()
    return DocumentRead.model_validate(await get_document(session, document.id))


@router.get("/{document_id}/download", response_model=DownloadRead)
async def download_document(
    document_id: UUID,
    version: int | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> DownloadRead:
    document = await get_document(session, document_id)
    await require_document_access(session, user, document)
    versions = document.versions
    selected = (
        next((item for item in versions if item.version_number == version), None)
        if version is not None
        else max(versions, key=lambda item: item.version_number, default=None)
    )
    if selected is None:
        raise HTTPException(status_code=404, detail="Document version not found")
    return DownloadRead(url=presigned_download_url(selected.object_key, selected.file_name))
