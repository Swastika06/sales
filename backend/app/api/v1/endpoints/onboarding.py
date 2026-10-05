import hashlib
import hmac
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import get_current_user
from app.core.security import verify_password
from app.db.session import get_db
from app.domain.access import is_tcg_admin, role_codes
from app.models.identity import Role, User
from app.models.onboarding import OnboardingApplication, OnboardingDocument, OnboardingMail
from app.models.partner import Partner, PartnerStatus
from app.schemas.onboarding import (
    ActivationCode,
    ApplicationAccess,
    LegalAssignment,
    LegalDecision,
    LegalReviewerCreate,
    OnboardingRegistrationRequest,
)
from app.services import onboarding as flow
from app.services.partners import create_partner, load_partner
from app.storage.client import presigned_download_url, put_private_object

router = APIRouter()
MAX_BYTES = 10 * 1024 * 1024


def client_ip(request: Request) -> str:
    # Forwarded headers are trusted only when configured on the ASGI server.
    return request.client.host if request.client else "unknown"


async def locked_application(session: AsyncSession, application_id: UUID) -> OnboardingApplication:
    application = await session.scalar(
        select(OnboardingApplication)
        .where(OnboardingApplication.id == application_id)
        .with_for_update()
    )
    if application is None:
        raise HTTPException(404, "Application not found")
    return application


async def response(
    session: AsyncSession, application: OnboardingApplication, *, staff: bool = False
) -> dict[str, Any]:
    partner = await session.get(Partner, application.partner_id)
    applicant = await session.get(User, application.applicant_id)
    if partner is None:
        raise HTTPException(409, "The application partner no longer exists")
    if applicant is None:
        raise HTTPException(409, "The application user no longer exists")
    docs = await flow.latest_documents(session, application.id)
    mail = await session.scalar(
        select(OnboardingMail)
        .where(OnboardingMail.application_id == application.id)
        .order_by(OnboardingMail.created_at.desc())
        .limit(1)
    )
    return {
        "id": application.id,
        "partner_id": partner.id,
        "company_name": partner.company_name,
        "email": applicant.email,
        "status": application.status,
        "revision": application.revision,
        "capabilities": [c.code for c in partner.capabilities],
        "assigned_to_id": application.assigned_to_id,
        "review_comment": application.review_comment,
        "submitted_at": application.submitted_at,
        "reviewed_at": application.reviewed_at,
        "verified_at": application.verified_at,
        "required_documents": list(flow.DOCUMENT_REQUIREMENTS)
        if flow.needs_documents([c.code for c in partner.capabilities])
        else [],
        "documents": [
            {
                "id": d.id,
                "kind": d.kind,
                "number": d.number,
                "filename": d.filename,
                "size": d.size,
                "revision": d.revision,
                "scan_status": d.scan_status,
            }
            for d in docs
        ],
        "mail_status": mail.status if mail else None,
        "mail_error": mail.last_error if mail and staff else None,
    }


@router.get("/requirements")
async def requirements() -> dict[str, Any]:
    return {
        "documents": [
            {"kind": k, "label": v["label"]} for k, v in flow.DOCUMENT_REQUIREMENTS.items()
        ],
        "capabilities": ["RESELLER", "REFERRAL"],
        "max_file_bytes": MAX_BYTES,
        "accepted_types": ["application/pdf", "image/png", "image/jpeg"],
    }


@router.post("/applications", status_code=201)
async def create(
    body: OnboardingRegistrationRequest, request: Request, session: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    await flow.limit(session, "create", client_ip(request), 20, 3600)
    # Registration no longer chooses a workspace password.
    import secrets

    body.password = secrets.token_urlsafe(24)
    partner, applicant = await create_partner(session, body, created_by=None, activate=False)
    application = await flow.create_application(session, partner, applicant)
    await flow.issue_onboarding_password(session, application)
    await session.commit()
    return {
        "token": flow.application_token(application),
        "application": await response(session, application),
    }


@router.post("/access")
async def access(
    body: ApplicationAccess, request: Request, session: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    await flow.limit(session, "access-ip", client_ip(request), 30, 900)
    await flow.limit(session, "access-email", str(body.email).lower(), 10, 900)
    user = await session.scalar(select(User).where(User.email == str(body.email).lower()))
    application = (
        await session.scalar(
            select(OnboardingApplication).where(OnboardingApplication.applicant_id == user.id)
        )
        if user
        else None
    )
    if user is None or application is None or application.status == "COMPLETED":
        raise HTTPException(401, "Unable to resume with these credentials")
    # Existing applications retain their original password until their five-day window ends.
    expires = application.access_expires_at or (
        flow.aware(application.created_at) + timedelta(days=5)
    )
    stored_hash = application.access_password_hash or user.hashed_password
    if flow.aware(expires) <= flow.now() or not verify_password(body.password, stored_hash):
        raise HTTPException(
            401, "Invalid or expired onboarding credentials. Contact the partner team."
        )
    return {
        "token": flow.application_token(application),
        "application": await response(session, application),
    }


@router.get("/me")
async def applicant_view(
    x_application_token: str = Header(), session: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    application = await flow.token_application(session, x_application_token)
    return await response(session, application)


@router.post("/me/documents", status_code=201)
async def upload(
    request: Request,
    kind: str = Form(...),
    number: str = Form(...),
    file: UploadFile = File(...),
    x_application_token: str = Header(),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    await flow.limit(session, "uploads-ip", client_ip(request), 60, 3600)
    application = await flow.token_application(session, x_application_token, lock=True)
    if application.status not in flow.EDITABLE:
        raise HTTPException(409, "Documents are locked while the application is under review")
    number = flow.validate_number(kind, number)
    data = await file.read(MAX_BYTES + 1)
    if not data or len(data) > MAX_BYTES:
        raise HTTPException(422, "Each document must be between 1 byte and 10 MB")
    filename = (file.filename or "").replace("\\", "/").split("/")[-1]
    if not filename or len(filename) > 200 or any(ord(c) < 32 for c in filename):
        raise HTTPException(422, "Invalid filename")
    content_type = flow.validate_file(filename, data)
    scan_status = await run_in_threadpool(flow.scan_file, data)
    object_key = f"onboarding/{application.id}/{uuid4()}"
    await run_in_threadpool(put_private_object, object_key, data, content_type)
    application.revision += 1
    document = OnboardingDocument(
        application_id=application.id,
        kind=kind,
        number=number,
        revision=application.revision,
        filename=filename,
        object_key=object_key,
        content_type=content_type,
        size=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        scan_status=scan_status,
    )
    session.add(document)
    await flow.audit(session, application, "DOCUMENT_UPLOADED", detail={"kind": kind})
    await session.commit()
    return await response(session, application)


@router.get("/me/documents/{document_id}/download")
async def applicant_download(
    document_id: UUID,
    x_application_token: str = Header(),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    application = await flow.token_application(session, x_application_token)
    document = await session.get(OnboardingDocument, document_id)
    if document is None or document.application_id != application.id:
        raise HTTPException(404, "Document not found")
    url = await run_in_threadpool(presigned_download_url, document.object_key, document.filename)
    applicant = await session.get(User, application.applicant_id)
    await flow.audit(
        session, application, "DOCUMENT_DOWNLOADED", applicant, {"document_id": str(document.id)}
    )
    await session.commit()
    return {"url": url}


@router.post("/me/submit")
async def submit(
    x_application_token: str = Header(), session: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    application = await flow.token_application(session, x_application_token, lock=True)
    if application.status == "PENDING_ADMIN_REVIEW":
        return await response(session, application)
    if application.status not in flow.EDITABLE:
        raise HTTPException(409, "This application cannot be submitted")
    await flow.validate_submission(session, application)
    application.status = "PENDING_ADMIN_REVIEW"
    application.submitted_at = flow.now()
    application.assigned_to_id = None
    application.reviewed_revision = None
    await flow.audit(session, application, "SUBMITTED")
    await session.commit()
    return await response(session, application)


@router.post("/me/resend")
async def resend(
    request: Request, x_application_token: str = Header(), session: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    await flow.limit(session, "resend-ip", client_ip(request), 30, 3600)
    application = await flow.token_application(session, x_application_token)
    await flow.limit(session, "resend-application", str(application.id), 5, 3600)
    application = await flow.token_application(session, x_application_token, lock=True)
    if application.status != "PENDING_EMAIL_VERIFICATION":
        raise HTTPException(409, "Email verification is available after legal approval")
    if (
        application.otp_sent_at
        and flow.aware(application.otp_sent_at) + timedelta(seconds=60) > flow.now()
    ):
        raise HTTPException(429, "Wait 60 seconds before requesting another code")
    await flow.queue_otp(session, application)
    await flow.audit(session, application, "OTP_REQUESTED")
    await session.commit()
    return {"message": "An activation email has been queued."}


@router.post("/me/verify")
async def verify(
    body: ActivationCode,
    request: Request,
    x_application_token: str = Header(),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    await flow.limit(session, "verify-ip", client_ip(request), 50, 900)
    application = await flow.token_application(session, x_application_token, lock=True)
    if application.status != "PENDING_EMAIL_VERIFICATION":
        raise HTTPException(409, "This application is not awaiting email verification")
    if (
        not application.otp_hash
        or not application.otp_expires_at
        or flow.aware(application.otp_expires_at) <= flow.now()
    ):
        raise HTTPException(422, "Your code has expired. Request another code.")
    if application.otp_attempts >= 5:
        raise HTTPException(429, "Too many incorrect codes. Request another code.")
    application.otp_attempts += 1
    valid = hmac.compare_digest(
        application.otp_hash, flow.digest(str(application.id) + ":" + body.code)
    )
    if not valid:
        await session.commit()
        raise HTTPException(422, "Incorrect activation code")
    if application.reviewed_revision != application.revision:
        raise HTTPException(409, "The current application has not been legally approved")
    partner = await load_partner(session, application.partner_id)
    if partner.status != PartnerStatus.PENDING_APPROVAL:
        raise HTTPException(409, "The partner is not awaiting activation")
    application.verified_at = flow.now()
    await flow.approve_partner(session, application)
    await flow.audit(session, application, "ACTIVATED")
    await session.commit()
    return {
        "message": "Account approved. Check your email for your temporary Partner Portal password."
    }


@router.get("/reviewers")
async def reviewers(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    flow.require_admin(user)
    rows = await session.scalars(
        select(User)
        .where(User.is_active.is_(True), User.roles.any(Role.code == "TCG_LEGAL"))
        .order_by(User.full_name)
    )
    return [{"id": row.id, "name": row.full_name, "email": row.email} for row in rows]


@router.post("/reviewers", status_code=201)
async def create_reviewer(
    body: LegalReviewerCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    from app.schemas.staff import StaffUserCreate
    from app.services.staff import create_staff_user

    reviewer = await create_staff_user(
        session,
        StaffUserCreate(email=body.email, full_name=body.full_name, role_code="TCG_LEGAL"),
        user,
    )
    await session.commit()
    return {"id": reviewer.id, "name": reviewer.full_name, "email": reviewer.email}


@router.get("/applications")
async def applications(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    query = (
        select(OnboardingApplication).order_by(OnboardingApplication.created_at.desc()).limit(200)
    )
    if not is_tcg_admin(user):
        if "TCG_LEGAL" not in role_codes(user):
            raise HTTPException(403, "Admin or Legal access is required")
        query = query.where(OnboardingApplication.assigned_to_id == user.id)
    return [await response(session, row, staff=True) for row in await session.scalars(query)]


@router.get("/applications/{application_id}")
async def detail(
    application_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    application = await locked_application(session, application_id)
    flow.require_staff_view(user, application)
    return await response(session, application, staff=True)


@router.post("/applications/{application_id}/assign-legal")
async def assign(
    application_id: UUID,
    body: LegalAssignment,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    flow.require_admin(user)
    application = await locked_application(session, application_id)
    if application.status not in {"PENDING_ADMIN_REVIEW", "LEGAL_REVIEW"}:
        raise HTTPException(409, "Only submitted applications can be assigned")
    reviewer = await session.get(User, body.reviewer_id)
    if reviewer is None or not reviewer.is_active or "TCG_LEGAL" not in role_codes(reviewer):
        raise HTTPException(422, "Select an active Legal reviewer")
    if reviewer.id == application.applicant_id:
        raise HTTPException(422, "An applicant cannot review their own application")
    await flow.validate_submission(session, application)
    application.assigned_to_id = reviewer.id
    application.status = "LEGAL_REVIEW"
    await flow.audit(session, application, "ASSIGNED", user, {"reviewer_id": str(reviewer.id)})
    await session.commit()
    return await response(session, application, staff=True)


@router.post("/applications/{application_id}/decision")
async def decision(
    application_id: UUID,
    body: LegalDecision,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    application = await locked_application(session, application_id)
    flow.require_reviewer(user, application)
    if application.status != "LEGAL_REVIEW" or body.revision != application.revision:
        raise HTTPException(409, "The application changed. Reload before recording a decision.")
    if body.decision != "APPROVE" and len(body.comment.strip()) < 3:
        raise HTTPException(422, "Explain the changes required or rejection reason")
    application.review_comment = body.comment.strip() or None
    application.reviewed_by_id = user.id
    application.reviewed_at = flow.now()
    application.reviewed_revision = application.revision
    if body.decision == "APPROVE":
        await flow.validate_submission(session, application)
        await flow.approve_partner(session, application)
    elif body.decision == "REQUEST_CHANGES":
        application.status = "CHANGES_REQUESTED"
        await flow.queue_mail(
            session, application, "CHANGES", "Legal requested changes: " + body.comment.strip()
        )
    else:
        application.status = "REJECTED"
        partner = await load_partner(session, application.partner_id)
        partner.status = PartnerStatus.REJECTED
        partner.rejection_reason = body.comment.strip()
        await flow.queue_mail(
            session,
            application,
            "REJECTED",
            "Your application was declined: " + body.comment.strip(),
        )
    await flow.audit(session, application, body.decision, user)
    await session.commit()
    return await response(session, application, staff=True)


@router.get("/applications/{application_id}/documents/{document_id}/download")
async def download(
    application_id: UUID,
    document_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    application = await locked_application(session, application_id)
    flow.require_staff_view(user, application)
    document = await session.get(OnboardingDocument, document_id)
    if document is None or document.application_id != application.id:
        raise HTTPException(404, "Document not found")
    url = await run_in_threadpool(presigned_download_url, document.object_key, document.filename)
    await flow.audit(
        session, application, "DOCUMENT_DOWNLOADED", user, {"document_id": str(document.id)}
    )
    await session.commit()
    return {"url": url}


@router.post("/partners/{partner_id}/start")
async def start_existing(
    partner_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    flow.require_admin(user)
    partner = await load_partner(session, partner_id)
    existing = await session.scalar(
        select(OnboardingApplication).where(OnboardingApplication.partner_id == partner_id)
    )
    if existing and existing.status != "COMPLETED":
        return await response(session, existing, staff=True)
    applicant = next(
        (u for u in partner.users if u.email == partner.primary_contact_email.lower()), None
    )
    if applicant is None:
        raise HTTPException(409, "The primary contact must have a user account")
    partner.status = PartnerStatus.PENDING_APPROVAL
    partner.approved_at = None
    partner.approved_by_id = None
    partner.rejection_reason = None
    for member in partner.users:
        member.is_active = False
    application = existing or await flow.create_application(session, partner, applicant)
    if existing:
        application.status = "DRAFT"
        application.token_version += 1
        application.revision += 1
        application.reviewed_revision = None
        application.assigned_to_id = None
        application.verified_at = None
        application.review_comment = None
        await flow.audit(session, application, "REOPENED", user)
    await flow.issue_onboarding_password(session, application)
    await session.commit()
    return await response(session, application, staff=True)
