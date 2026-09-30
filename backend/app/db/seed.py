import asyncio
from collections.abc import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal, close_db
from app.models.identity import Permission, Role, User
from app.models.partner import Country, PartnerType
from app.models.pricing import (
    Product,
    Sku,
    SkuCategory,
)
from app.models.seed import SeedRecord

SeedFunction = Callable[[AsyncSession], Awaitable[None]]

ROLE_DEFINITIONS = {
    "TCG_ADMIN": "TCG Admin",
    "TCG_SALES": "TCG Sales",
    "PARTNER_ADMIN": "Partner Admin",
    "PARTNER_SALES": "Partner Sales",
    "PARTNER_PRESALES": "Partner Pre-Sales",
    "PARTNER_DELIVERY": "Partner Delivery",
}

PERMISSION_DEFINITIONS = {
    "platform.manage": "Manage platform configuration and identity",
    "partners.manage": "Create, review, and manage partners",
    "partners.view": "View authorized partner data",
    "partners.approve": "Approve or reject partner registrations",
    "partner_profile.manage": "Manage an authorized partner profile",
    "partner_users.manage": "Manage users for an authorized partner",
    "sales.manage": "Manage deals, quotes, and orders",
    "sales.view": "View authorized sales data",
    "documents.manage": "Publish and administer documents",
    "documents.view": "View authorized documents",
    "catalog.view": "View the product and SKU catalog",
    "catalog.manage": "Create and manage products and SKUs",
    "pricing.view": "View authorized resolved pricing",
    "pricing.manage": "Configure price masters, rules, and overrides",
}

PARTNER_TYPE_DEFINITIONS = {
    "RESELLER": ("Reseller", "Resells TCG products to customers"),
    "REFERRAL": ("Referral", "Introduces qualified customer opportunities"),
    "SYSTEM_INTEGRATOR": ("System Integrator", "Implements and integrates TCG products"),
}


COUNTRY_DEFINITIONS = {
    "AU": "Australia",
    "BR": "Brazil",
    "CA": "Canada",
    "CN": "China",
    "DE": "Germany",
    "ES": "Spain",
    "FR": "France",
    "GB": "United Kingdom",
    "ID": "Indonesia",
    "IN": "India",
    "IT": "Italy",
    "JP": "Japan",
    "KE": "Kenya",
    "KR": "South Korea",
    "MX": "Mexico",
    "MY": "Malaysia",
    "NG": "Nigeria",
    "NL": "Netherlands",
    "NZ": "New Zealand",
    "PH": "Philippines",
    "SA": "Saudi Arabia",
    "SG": "Singapore",
    "TH": "Thailand",
    "US": "United States",
    "VN": "Vietnam",
    "ZA": "South Africa",
}


async def seed_identity(session: AsyncSession) -> None:
    permissions: dict[str, Permission] = {}
    for code, description in PERMISSION_DEFINITIONS.items():
        existing = await session.scalar(select(Permission).where(Permission.code == code))
        permission = existing or Permission(code=code, description=description)
        if existing is None:
            session.add(permission)
        permissions[code] = permission

    await session.flush()
    roles: dict[str, Role] = {}
    for code, name in ROLE_DEFINITIONS.items():
        existing = await session.scalar(
            select(Role).where(Role.code == code).options(selectinload(Role.permissions))
        )
        role = existing or Role(code=code, name=name, permissions=[])
        role.name = name
        if existing is None:
            session.add(role)
        roles[code] = role

    await session.flush()
    roles["TCG_ADMIN"].permissions = list(permissions.values())
    roles["TCG_SALES"].permissions = [
        permissions["partners.view"],
        permissions["catalog.view"],
        permissions["pricing.view"],
        permissions["sales.manage"],
        permissions["documents.view"],
    ]
    roles["PARTNER_ADMIN"].permissions = [
        permissions["partners.view"],
        permissions["sales.manage"],
        permissions["documents.view"],
    ]
    roles["PARTNER_SALES"].permissions = [
        permissions["sales.manage"],
        permissions["documents.view"],
    ]
    for code in ("PARTNER_PRESALES", "PARTNER_DELIVERY"):
        roles[code].permissions = [permissions["sales.view"], permissions["documents.view"]]

    email = settings.SEED_ADMIN_EMAIL.lower()
    admin = await session.scalar(
        select(User).where(User.email == email).options(selectinload(User.roles))
    )
    if admin is None:
        admin = User(
            email=email,
            full_name=settings.SEED_ADMIN_NAME,
            hashed_password=hash_password(settings.SEED_ADMIN_PASSWORD),
            is_active=True,
            is_superuser=True,
            roles=[],
        )
        session.add(admin)
    if roles["TCG_ADMIN"] not in admin.roles:
        admin.roles.append(roles["TCG_ADMIN"])


async def seed_partner_master_data(session: AsyncSession) -> None:
    permissions: dict[str, Permission] = {}
    for code, description in PERMISSION_DEFINITIONS.items():
        permission = await session.scalar(select(Permission).where(Permission.code == code))
        if permission is None:
            permission = Permission(code=code, description=description)
            session.add(permission)
        else:
            permission.description = description
        permissions[code] = permission
    await session.flush()

    roles: dict[str, Role] = {}
    for code, name in ROLE_DEFINITIONS.items():
        role = await session.scalar(
            select(Role).where(Role.code == code).options(selectinload(Role.permissions))
        )
        if role is None:
            role = Role(code=code, name=name, permissions=[])
            session.add(role)
        roles[code] = role
    await session.flush()
    roles["TCG_ADMIN"].permissions = list(permissions.values())
    roles["TCG_SALES"].permissions = [
        permissions["partners.view"],
        permissions["catalog.view"],
        permissions["pricing.view"],
        permissions["sales.manage"],
        permissions["documents.view"],
    ]
    roles["PARTNER_ADMIN"].permissions = [
        permissions["partners.view"],
        permissions["partner_profile.manage"],
        permissions["partner_users.manage"],
        permissions["catalog.view"],
        permissions["pricing.view"],
        permissions["sales.manage"],
        permissions["documents.view"],
    ]
    roles["PARTNER_SALES"].permissions = [
        permissions["partners.view"],
        permissions["catalog.view"],
        permissions["pricing.view"],
        permissions["sales.manage"],
        permissions["documents.view"],
    ]
    for code in ("PARTNER_PRESALES", "PARTNER_DELIVERY"):
        roles[code].permissions = [
            permissions["partners.view"],
            permissions["catalog.view"],
            permissions["pricing.view"],
            permissions["sales.view"],
            permissions["documents.view"],
        ]

    for code, (name, description) in PARTNER_TYPE_DEFINITIONS.items():
        value = await session.scalar(select(PartnerType).where(PartnerType.code == code))
        if value is None:
            session.add(PartnerType(code=code, name=name, description=description))
        else:
            value.name, value.description, value.is_active = name, description, True

    for code, name in COUNTRY_DEFINITIONS.items():
        value = await session.scalar(select(Country).where(Country.code == code))
        if value is None:
            session.add(Country(code=code, name=name))
        else:
            value.name, value.is_active = name, True


async def seed_product_pricing(session: AsyncSession) -> None:
    await seed_partner_master_data(session)
    product_definitions = {
        "MCUBE": ("mcube", "TCG Digital mcube product family"),
        "LVA": ("LVA", "TCG Digital LVA product family"),
    }
    sku_definitions = {
        "MCUBE": (
            ("MCUBE-LICENSE", "mcube License", SkuCategory.LICENSE, "license"),
            (
                "MCUBE-IMPLEMENTATION",
                "mcube Implementation",
                SkuCategory.IMPLEMENTATION,
                "project",
            ),
        ),
        "LVA": (
            ("LVA-LICENSE", "LVA License", SkuCategory.LICENSE, "license"),
            (
                "LVA-IMPLEMENTATION",
                "LVA Implementation",
                SkuCategory.IMPLEMENTATION,
                "project",
            ),
        ),
    }
    for code, (name, description) in product_definitions.items():
        product = await session.scalar(
            select(Product).where(Product.code == code).options(selectinload(Product.skus))
        )
        if product is None:
            product = Product(code=code, name=name, description=description, skus=[])
            session.add(product)
            await session.flush()
        else:
            product.name, product.description, product.is_active = name, description, True
        existing_skus = {sku.code: sku for sku in product.skus}
        for sku_code, sku_name, category, unit in sku_definitions[code]:
            sku = existing_skus.get(sku_code)
            if sku is None:
                product.skus.append(Sku(code=sku_code, name=sku_name, category=category, unit=unit))
            else:
                sku.name, sku.category, sku.unit, sku.is_active = (
                    sku_name,
                    category,
                    unit,
                    True,
                )


async def seed_mcube_display_name(session: AsyncSession) -> None:
    product = await session.scalar(
        select(Product).where(Product.code == "MCUBE").options(selectinload(Product.skus))
    )
    if product is None:
        return
    from app.services.commercial import tcg_organization

    product.owner_organization_id = (await tcg_organization(session)).id
    product.name = "mcube"
    product.description = "TCG Digital mcube product family"
    sku_names = {
        "MCUBE-LICENSE": "mcube License",
        "MCUBE-IMPLEMENTATION": "mcube Implementation",
    }
    for sku in product.skus:
        if sku.code in sku_names:
            sku.name = sku_names[sku.code]


SEEDS: tuple[tuple[str, SeedFunction], ...] = (
    ("foundation-identity-v1", seed_identity),
    ("phase-1a-partner-master-data-v1", seed_partner_master_data),
    ("phase-1b-product-pricing-v1", seed_product_pricing),
    ("phase-1-remaining-permissions-v1", seed_partner_master_data),
    ("phase-1-mcube-display-name-v1", seed_mcube_display_name),
    ("commercial-model-owner-v1", seed_mcube_display_name),
)


async def run_seeds() -> None:
    async with SessionLocal() as session:
        for key, seed_function in SEEDS:
            if await session.get(SeedRecord, key):
                print(f"Skipped seed {key} (already applied)")
                continue
            async with session.begin_nested():
                await seed_function(session)
                session.add(SeedRecord(key=key))
            await session.commit()
            print(f"Applied seed {key}")


async def async_main() -> None:
    try:
        await run_seeds()
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(async_main())
