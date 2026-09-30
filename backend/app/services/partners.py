from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import hash_password
from app.models.commercial import Organization
from app.models.identity import Role, User
from app.models.partner import Country, Partner, PartnerStatus, PartnerType
from app.schemas.partner import AdminPartnerCreate, PartnerRegistrationRequest


async def get_partner_type(session: AsyncSession, code: str) -> PartnerType:
    value = await session.scalar(
        select(PartnerType).where(PartnerType.code == code, PartnerType.is_active.is_(True))
    )
    if value is None:
        raise HTTPException(status_code=422, detail=f"Unknown partner type: {code}")
    return value


async def get_countries(session: AsyncSession, codes: list[str]) -> list[Country]:
    result = await session.scalars(
        select(Country).where(Country.code.in_(codes), Country.is_active.is_(True))
    )
    countries = list(result)
    found = {country.code for country in countries}
    missing = sorted(set(codes) - found)
    if missing:
        raise HTTPException(
            status_code=422, detail=f"Unknown country code(s): {', '.join(missing)}"
        )
    countries.sort(key=lambda country: codes.index(country.code))
    return countries


async def get_roles(session: AsyncSession, codes: list[str]) -> list[Role]:
    result = await session.scalars(select(Role).where(Role.code.in_(codes)))
    roles = list(result)
    found = {role.code for role in roles}
    missing = sorted(set(codes) - found)
    if missing:
        raise HTTPException(status_code=422, detail=f"Unknown role(s): {', '.join(missing)}")
    return roles


async def ensure_email_available(session: AsyncSession, email: str) -> None:
    if await session.scalar(select(User.id).where(User.email == email.lower())):
        raise HTTPException(status_code=409, detail="A user with this email already exists")


async def load_partner(session: AsyncSession, partner_id: UUID) -> Partner:
    partner = await session.scalar(
        select(Partner)
        .where(Partner.id == partner_id)
        .options(
            selectinload(Partner.countries),
            selectinload(Partner.users).selectinload(User.roles),
        )
    )
    if partner is None:
        raise HTTPException(status_code=404, detail="Partner not found")
    return partner


async def create_partner(
    session: AsyncSession,
    payload: PartnerRegistrationRequest | AdminPartnerCreate,
    *,
    created_by: User | None,
    activate: bool,
) -> tuple[Partner, User]:
    email = str(payload.primary_contact_email).lower()
    await ensure_email_available(session, email)
    capabilities = [await get_partner_type(session, code) for code in payload.capability_codes]
    partner_type = capabilities[0]
    countries = await get_countries(session, payload.country_codes)
    organization = None
    if isinstance(payload, AdminPartnerCreate) and payload.organization_id:
        organization = await session.get(Organization, payload.organization_id)
        if organization is None or not organization.is_active:
            raise HTTPException(422, "Select an active organization")
        if await session.scalar(
            select(Partner.id).where(Partner.organization_id == organization.id)
        ):
            raise HTTPException(409, "This organization already has a partner profile")
    if organization is None:
        from uuid import uuid4

        organization = Organization(
            legal_name=payload.legal_name or payload.company_name,
            identifier=f"partner:{uuid4()}",
        )
        session.add(organization)
        await session.flush()
    partner_admin_role = (await get_roles(session, ["PARTNER_ADMIN"]))[0]
    partner = Partner(
        company_name=payload.company_name.strip(),
        legal_name=payload.legal_name.strip() if payload.legal_name else None,
        company_email=str(payload.company_email).lower(),
        website=str(payload.website) if payload.website else None,
        phone=payload.phone,
        address=payload.address,
        primary_contact_name=payload.primary_contact_name.strip(),
        primary_contact_email=email,
        primary_contact_phone=payload.primary_contact_phone,
        partner_type=partner_type,
        capabilities=capabilities,
        organization_id=organization.id,
        countries=countries,
        users=[],
        status=PartnerStatus.ACTIVE if activate else PartnerStatus.PENDING_APPROVAL,
        created_by_id=created_by.id if created_by else None,
        approved_by_id=created_by.id if activate and created_by else None,
        approved_at=datetime.now(UTC) if activate else None,
    )
    session.add(partner)
    await session.flush()
    partner.code = f"PTN-{partner.id.hex[:8].upper()}" if activate else None
    user = User(
        email=email,
        full_name=payload.primary_contact_name.strip(),
        hashed_password=hash_password(payload.password),
        is_active=activate,
        is_superuser=False,
        partner_id=partner.id,
        roles=[partner_admin_role],
    )
    session.add(user)
    partner.users.append(user)
    return partner, user
