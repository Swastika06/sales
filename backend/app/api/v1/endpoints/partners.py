from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_current_user
from app.core.security import hash_password
from app.db.session import get_db
from app.domain.access import (
    PARTNER_ROLE_CODES,
    can_manage_partner,
    can_view_partner,
    is_tcg_admin,
    is_tcg_user,
    role_codes,
)
from app.models.identity import Role, User
from app.models.onboarding import OnboardingApplication
from app.models.partner import Country, Partner, PartnerStatus, PartnerType
from app.schemas.partner import (
    AdminPartnerCreate,
    MasterDataItem,
    PartnerDecisionRequest,
    PartnerListResponse,
    PartnerRead,
    PartnerRegistrationRequest,
    PartnerRejectionRequest,
    PartnerStatusUpdate,
    PartnerUpdate,
    PartnerUserCreate,
    PartnerUserRead,
    PartnerUserUpdate,
    RegistrationOptions,
)
from app.services import onboarding as onboarding_flow
from app.services.audit import record_audit_event
from app.services.partners import (
    create_partner,
    ensure_email_available,
    get_countries,
    get_partner_type,
    get_roles,
    load_partner,
)

router = APIRouter()


def actor_role(user: User) -> str | None:
    return sorted(role_codes(user))[0] if user.roles else None


def partner_response(partner: Partner) -> PartnerRead:
    return PartnerRead.model_validate(partner)


def user_response(user: User) -> PartnerUserRead:
    return PartnerUserRead(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        roles=sorted(role.code for role in user.roles),
        created_at=user.created_at,
    )


def require_tcg_admin(user: User) -> None:
    if not is_tcg_admin(user):
        raise HTTPException(status_code=403, detail="TCG Admin access is required")


def require_partner_view(user: User, partner_id: UUID) -> None:
    if not can_view_partner(user, partner_id):
        raise HTTPException(status_code=403, detail="You cannot access this partner")


def require_partner_management(user: User, partner_id: UUID) -> None:
    if not can_manage_partner(user, partner_id):
        raise HTTPException(status_code=403, detail="Partner management access is required")


@router.get("/registration-options", response_model=RegistrationOptions)
async def registration_options(session: AsyncSession = Depends(get_db)) -> RegistrationOptions:
    partner_types = list(
        await session.scalars(
            select(PartnerType).where(PartnerType.is_active.is_(True)).order_by(PartnerType.name)
        )
    )
    countries = list(
        await session.scalars(
            select(Country).where(Country.is_active.is_(True)).order_by(Country.name)
        )
    )
    partner_roles = list(
        await session.scalars(
            select(Role).where(Role.code.in_(PARTNER_ROLE_CODES)).order_by(Role.name)
        )
    )
    return RegistrationOptions(
        partner_types=[MasterDataItem.model_validate(value) for value in partner_types],
        countries=[MasterDataItem.model_validate(value) for value in countries],
        partner_roles=[MasterDataItem.model_validate(value) for value in partner_roles],
    )


@router.post("/register", response_model=PartnerRead, status_code=status.HTTP_201_CREATED)
async def self_register(
    payload: PartnerRegistrationRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> PartnerRead:
    if onboarding_flow.needs_documents(payload.capability_codes):
        raise HTTPException(
            409, "Use the onboarding form to upload documents and submit for legal review"
        )
    partner, user = await create_partner(session, payload, created_by=None, activate=False)
    await record_audit_event(
        session,
        action="PARTNER_SELF_REGISTERED",
        entity_type="partner",
        entity_id=str(partner.id),
        new_values={"company_name": partner.company_name, "primary_user_id": str(user.id)},
        request_id=request.state.request_id,
    )
    await session.commit()
    return partner_response(await load_partner(session, partner.id))


@router.post("", response_model=PartnerRead, status_code=status.HTTP_201_CREATED)
async def admin_create_partner(
    payload: AdminPartnerCreate,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> PartnerRead:
    require_tcg_admin(user)
    requires_review = onboarding_flow.needs_documents(payload.capability_codes)
    partner, primary_user = await create_partner(
        session, payload, created_by=user, activate=not requires_review
    )
    if requires_review:
        application = await onboarding_flow.create_application(session, partner, primary_user)
        await onboarding_flow.queue_mail(
            session,
            application,
            "DRAFT",
            "Please upload your company documents and submit your partner application for review.",
        )
    await record_audit_event(
        session,
        action="PARTNER_CREATED",
        entity_type="partner",
        entity_id=str(partner.id),
        actor_user_id=user.id,
        actor_role=actor_role(user),
        new_values={
            "company_name": partner.company_name,
            "status": partner.status,
            "primary_user_id": str(primary_user.id),
        },
        request_id=request.state.request_id,
    )
    await session.commit()
    return partner_response(await load_partner(session, partner.id))


@router.get("", response_model=PartnerListResponse)
async def list_partners(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=100),
    partner_status: PartnerStatus | None = Query(default=None, alias="status"),
    partner_type: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> PartnerListResponse:
    statement = select(Partner).options(selectinload(Partner.countries))
    count_statement = select(func.count()).select_from(Partner)
    filters = []
    if not is_tcg_user(user):
        if user.partner_id is None:
            return PartnerListResponse(items=[], total=0, page=page, page_size=page_size)
        filters.append(Partner.id == user.partner_id)
    if search:
        term = f"%{search.strip()}%"
        filters.append(or_(Partner.company_name.ilike(term), Partner.code.ilike(term)))
    if partner_status:
        filters.append(Partner.status == partner_status)
    if partner_type:
        filters.append(Partner.capabilities.any(code=partner_type.upper()))
    if filters:
        statement = statement.where(*filters)
        count_statement = count_statement.where(*filters)
    total = int(await session.scalar(count_statement) or 0)
    partners = list(
        await session.scalars(
            statement.order_by(Partner.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return PartnerListResponse(
        items=[partner_response(partner) for partner in partners],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{partner_id}", response_model=PartnerRead)
async def get_partner(
    partner_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> PartnerRead:
    require_partner_view(user, partner_id)
    return partner_response(await load_partner(session, partner_id))


@router.patch("/{partner_id}", response_model=PartnerRead)
async def update_partner(
    partner_id: UUID,
    payload: PartnerUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> PartnerRead:
    require_partner_management(user, partner_id)
    partner = await load_partner(session, partner_id)
    changes = payload.model_dump(exclude_unset=True)
    application = await session.scalar(
        select(OnboardingApplication)
        .where(OnboardingApplication.partner_id == partner.id)
        .with_for_update()
    )
    if application and application.status not in {"DRAFT", "CHANGES_REQUESTED", "COMPLETED"}:
        raise HTTPException(409, "The application is locked during review")
    if (
        application
        and "primary_contact_email" in changes
        and (str(changes["primary_contact_email"]).lower() != partner.primary_contact_email.lower())
    ):
        raise HTTPException(409, "The applicant email cannot be changed through profile editing")
    new_codes = changes.get("capability_codes") or (
        [changes["partner_type_code"]] if changes.get("partner_type_code") else []
    )
    if onboarding_flow.needs_documents(new_codes) and not application:
        raise HTTPException(
            409, "Start document review before adding Reseller or Referral capabilities"
        )
    if (
        application
        and application.status == "COMPLETED"
        and (new_codes and set(new_codes) != {c.code for c in partner.capabilities})
    ):
        raise HTTPException(
            409, "Start a new document review before changing verified capabilities"
        )
    controlled = {"partner_type_code", "capability_codes"}
    if not is_tcg_admin(user) and controlled & changes.keys():
        raise HTTPException(status_code=403, detail="Only TCG Admin can change capabilities")
    old_values = {
        key: getattr(partner, key, None)
        for key in changes
        if key not in {"country_codes", "partner_type_code", "capability_codes"}
    }
    if "partner_type_code" in changes:
        partner.partner_type = await get_partner_type(session, changes.pop("partner_type_code"))
        partner.capabilities = [partner.partner_type]
    if "capability_codes" in changes:
        codes = changes.pop("capability_codes")
        if codes is None:
            raise HTTPException(422, "Capabilities cannot be null")
        partner.capabilities = [
            await get_partner_type(session, code.strip().upper()) for code in dict.fromkeys(codes)
        ]
        partner.partner_type = partner.capabilities[0]
    if "country_codes" in changes:
        partner.countries = await get_countries(session, changes.pop("country_codes"))
    for key, value in changes.items():
        if key in {"company_email", "primary_contact_email"} and value is not None:
            value = str(value).lower()
        if key == "website" and value is not None:
            value = str(value)
        setattr(partner, key, value)
    await record_audit_event(
        session,
        action="PARTNER_UPDATED",
        entity_type="partner",
        entity_id=str(partner.id),
        actor_user_id=user.id,
        actor_role=actor_role(user),
        old_values=old_values,
        new_values=payload.model_dump(mode="json", exclude_unset=True),
        request_id=request.state.request_id,
    )
    await session.commit()
    return partner_response(await load_partner(session, partner.id))


@router.post("/{partner_id}/approve", response_model=PartnerRead)
async def approve_partner(
    partner_id: UUID,
    payload: PartnerDecisionRequest,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> PartnerRead:
    require_tcg_admin(user)
    partner = await load_partner(session, partner_id)
    await onboarding_flow.activation_guard(session, partner.id)
    if onboarding_flow.needs_documents([c.code for c in partner.capabilities]):
        raise HTTPException(
            409, "Use document review and email verification to activate this partner"
        )
    if partner.status != PartnerStatus.PENDING_APPROVAL:
        raise HTTPException(status_code=409, detail="Only pending partners can be approved")
    partner.status = PartnerStatus.ACTIVE
    partner.rejection_reason = None
    partner.approved_by_id = user.id
    partner.approved_at = datetime.now(UTC)
    partner.code = partner.code or f"PTN-{partner.id.hex[:8].upper()}"
    for partner_user in partner.users:
        partner_user.is_active = True
    await record_audit_event(
        session,
        action="PARTNER_APPROVED",
        entity_type="partner",
        entity_id=str(partner.id),
        actor_user_id=user.id,
        actor_role=actor_role(user),
        old_values={"status": PartnerStatus.PENDING_APPROVAL},
        new_values={
            "status": PartnerStatus.ACTIVE,
            "capabilities": [c.code for c in partner.capabilities],
        },
        request_id=request.state.request_id,
    )
    await session.commit()
    return partner_response(await load_partner(session, partner.id))


@router.post("/{partner_id}/reject", response_model=PartnerRead)
async def reject_partner(
    partner_id: UUID,
    payload: PartnerRejectionRequest,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> PartnerRead:
    require_tcg_admin(user)
    partner = await load_partner(session, partner_id)
    await onboarding_flow.activation_guard(session, partner.id)
    if partner.status != PartnerStatus.PENDING_APPROVAL:
        raise HTTPException(status_code=409, detail="Only pending partners can be rejected")
    partner.status = PartnerStatus.REJECTED
    partner.rejection_reason = payload.reason.strip()
    for partner_user in partner.users:
        partner_user.is_active = False
    await record_audit_event(
        session,
        action="PARTNER_REJECTED",
        entity_type="partner",
        entity_id=str(partner.id),
        actor_user_id=user.id,
        actor_role=actor_role(user),
        old_values={"status": PartnerStatus.PENDING_APPROVAL},
        new_values={"status": PartnerStatus.REJECTED, "reason": partner.rejection_reason},
        request_id=request.state.request_id,
    )
    await session.commit()
    return partner_response(await load_partner(session, partner.id))


@router.post("/{partner_id}/status", response_model=PartnerRead)
async def update_partner_status(
    partner_id: UUID,
    payload: PartnerStatusUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> PartnerRead:
    require_tcg_admin(user)
    if payload.status not in {
        PartnerStatus.ACTIVE,
        PartnerStatus.SUSPENDED,
        PartnerStatus.INACTIVE,
    }:
        raise HTTPException(status_code=422, detail="Unsupported status transition")
    partner = await load_partner(session, partner_id)
    if partner.status in {PartnerStatus.PENDING_APPROVAL, PartnerStatus.REJECTED}:
        raise HTTPException(status_code=409, detail="Use the approval workflow for this partner")
    if payload.status == PartnerStatus.ACTIVE:
        await onboarding_flow.activation_guard(session, partner.id)
    old_status = partner.status
    partner.status = payload.status
    for partner_user in partner.users:
        partner_user.is_active = payload.status == PartnerStatus.ACTIVE
    await record_audit_event(
        session,
        action="PARTNER_STATUS_CHANGED",
        entity_type="partner",
        entity_id=str(partner.id),
        actor_user_id=user.id,
        actor_role=actor_role(user),
        old_values={"status": old_status},
        new_values={"status": payload.status},
        request_id=request.state.request_id,
    )
    await session.commit()
    return partner_response(await load_partner(session, partner.id))


@router.get("/{partner_id}/users", response_model=list[PartnerUserRead])
async def list_partner_users(
    partner_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[PartnerUserRead]:
    require_partner_view(user, partner_id)
    partner = await load_partner(session, partner_id)
    return [user_response(partner_user) for partner_user in partner.users]


@router.post(
    "/{partner_id}/users", response_model=PartnerUserRead, status_code=status.HTTP_201_CREATED
)
async def create_partner_user(
    partner_id: UUID,
    payload: PartnerUserCreate,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> PartnerUserRead:
    require_partner_management(user, partner_id)
    partner = await load_partner(session, partner_id)
    if partner.status != PartnerStatus.ACTIVE:
        raise HTTPException(status_code=409, detail="Users can only be added to active partners")
    invalid_roles = set(payload.role_codes) - PARTNER_ROLE_CODES
    if invalid_roles:
        raise HTTPException(status_code=422, detail="Only partner roles can be assigned")
    email = str(payload.email).lower()
    await ensure_email_available(session, email)
    roles = await get_roles(session, payload.role_codes)
    new_user = User(
        email=email,
        full_name=payload.full_name.strip(),
        hashed_password=hash_password(payload.password),
        is_active=True,
        is_superuser=False,
        partner_id=partner.id,
        roles=roles,
    )
    session.add(new_user)
    await session.flush()
    await record_audit_event(
        session,
        action="PARTNER_USER_CREATED",
        entity_type="user",
        entity_id=str(new_user.id),
        actor_user_id=user.id,
        actor_role=actor_role(user),
        new_values={"partner_id": str(partner.id), "roles": payload.role_codes},
        request_id=request.state.request_id,
    )
    await session.commit()
    return user_response(new_user)


@router.patch("/{partner_id}/users/{user_id}", response_model=PartnerUserRead)
async def update_partner_user(
    partner_id: UUID,
    user_id: UUID,
    payload: PartnerUserUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> PartnerUserRead:
    require_partner_management(user, partner_id)
    partner = await load_partner(session, partner_id)
    target = next((member for member in partner.users if member.id == user_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail="Partner user not found")
    if payload.is_active is False and target.id == user.id:
        raise HTTPException(status_code=409, detail="You cannot deactivate your own account")
    if payload.is_active is True and partner.status != PartnerStatus.ACTIVE:
        raise HTTPException(
            status_code=409, detail="A suspended or inactive partner cannot have active users"
        )
    removes_admin = "PARTNER_ADMIN" in role_codes(target) and (
        payload.is_active is False
        or (payload.role_codes is not None and "PARTNER_ADMIN" not in payload.role_codes)
    )
    if removes_admin and not any(
        member.id != target.id and member.is_active and "PARTNER_ADMIN" in role_codes(member)
        for member in partner.users
    ):
        raise HTTPException(
            status_code=409, detail="The partner must retain an active administrator"
        )
    old_values = {
        "full_name": target.full_name,
        "is_active": target.is_active,
        "roles": sorted(role.code for role in target.roles),
    }
    if payload.full_name is not None:
        target.full_name = payload.full_name.strip()
    if payload.is_active is not None:
        target.is_active = payload.is_active
    if payload.role_codes is not None:
        if set(payload.role_codes) - PARTNER_ROLE_CODES:
            raise HTTPException(status_code=422, detail="Only partner roles can be assigned")
        target.roles = await get_roles(session, payload.role_codes)
    await record_audit_event(
        session,
        action="PARTNER_USER_UPDATED",
        entity_type="user",
        entity_id=str(target.id),
        actor_user_id=user.id,
        actor_role=actor_role(user),
        old_values=old_values,
        new_values=payload.model_dump(mode="json", exclude_unset=True),
        request_id=request.state.request_id,
    )
    await session.commit()
    return user_response(target)
