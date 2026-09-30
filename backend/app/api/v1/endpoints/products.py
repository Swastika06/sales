from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.domain.access import is_tcg_admin, is_tcg_user, role_codes
from app.models.identity import User
from app.models.pricing import Product, ProductPrice, Sku
from app.schemas.pricing import (
    ProductCreate,
    ProductPriceCreate,
    ProductPriceRead,
    ProductRead,
    ProductUpdate,
    SkuCreate,
    SkuRead,
    SkuUpdate,
)
from app.services.audit import record_audit_event

router = APIRouter()


def require_tcg_admin(user: User) -> None:
    if not is_tcg_admin(user):
        raise HTTPException(status_code=403, detail="TCG Admin access is required")


def actor_role(user: User) -> str | None:
    return sorted(role_codes(user))[0] if user.roles else None


async def get_product_or_404(session: AsyncSession, product_id: UUID) -> Product:
    product = await session.scalar(
        select(Product).where(Product.id == product_id).options(selectinload(Product.skus))
    )
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


async def get_sku_or_404(session: AsyncSession, sku_id: UUID) -> Sku:
    sku = await session.get(Sku, sku_id)
    if sku is None:
        raise HTTPException(status_code=404, detail="SKU not found")
    return sku


@router.get("", response_model=list[ProductRead])
async def list_products(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[ProductRead]:
    statement = select(Product).order_by(Product.name)
    if not is_tcg_user(user):
        statement = statement.where(Product.is_active.is_(True)).options(
            selectinload(Product.skus.and_(Sku.is_active.is_(True)))
        )
    else:
        statement = statement.options(selectinload(Product.skus))
    products = list(await session.scalars(statement))
    return [ProductRead.model_validate(product) for product in products]


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreate,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ProductRead:
    require_tcg_admin(user)
    if await session.scalar(select(Product.id).where(Product.code == payload.code)):
        raise HTTPException(status_code=409, detail="Product code already exists")
    from app.models.commercial import Organization
    from app.services.commercial import tcg_organization

    tcg = await tcg_organization(session)
    owner = payload.owner_organization_id or tcg.id
    organization = await session.get(Organization, owner)
    if organization is None or not organization.is_active:
        raise HTTPException(422, "Select an active product owner organization")
    if payload.code == "MCUBE" and owner != tcg.id:
        raise HTTPException(422, "TCG owns mcube")
    product = Product(
        owner_organization_id=owner,
        code=payload.code,
        name=payload.name.strip(),
        description=payload.description,
        skus=[],
    )
    session.add(product)
    await session.flush()
    await record_audit_event(
        session,
        action="PRODUCT_CREATED",
        entity_type="product",
        entity_id=str(product.id),
        actor_user_id=user.id,
        actor_role=actor_role(user),
        new_values=payload.model_dump(mode="json"),
        request_id=request.state.request_id,
    )
    await session.commit()
    return ProductRead.model_validate(product)


@router.patch("/{product_id}", response_model=ProductRead)
async def update_product(
    product_id: UUID,
    payload: ProductUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ProductRead:
    require_tcg_admin(user)
    product = await get_product_or_404(session, product_id)
    changes = payload.model_dump(exclude_unset=True)
    old_values = {key: getattr(product, key) for key in changes}
    for key, value in changes.items():
        setattr(product, key, value.strip() if isinstance(value, str) else value)
    await record_audit_event(
        session,
        action="PRODUCT_UPDATED",
        entity_type="product",
        entity_id=str(product.id),
        actor_user_id=user.id,
        actor_role=actor_role(user),
        old_values=old_values,
        new_values=payload.model_dump(mode="json", exclude_unset=True),
        request_id=request.state.request_id,
    )
    await session.commit()
    return ProductRead.model_validate(product)


@router.post("/{product_id}/skus", response_model=SkuRead, status_code=status.HTTP_201_CREATED)
async def create_sku(
    product_id: UUID,
    payload: SkuCreate,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> SkuRead:
    require_tcg_admin(user)
    await get_product_or_404(session, product_id)
    if await session.scalar(select(Sku.id).where(Sku.code == payload.code)):
        raise HTTPException(status_code=409, detail="SKU code already exists")
    sku = Sku(product_id=product_id, **payload.model_dump())
    session.add(sku)
    await session.flush()
    await record_audit_event(
        session,
        action="SKU_CREATED",
        entity_type="sku",
        entity_id=str(sku.id),
        actor_user_id=user.id,
        actor_role=actor_role(user),
        new_values=payload.model_dump(mode="json") | {"product_id": str(product_id)},
        request_id=request.state.request_id,
    )
    await session.commit()
    return SkuRead.model_validate(sku)


@router.patch("/skus/{sku_id}", response_model=SkuRead)
async def update_sku(
    sku_id: UUID,
    payload: SkuUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> SkuRead:
    require_tcg_admin(user)
    sku = await get_sku_or_404(session, sku_id)
    changes = payload.model_dump(exclude_unset=True)
    old_values = {key: getattr(sku, key) for key in changes}
    for key, value in changes.items():
        setattr(sku, key, value.strip() if isinstance(value, str) else value)
    await record_audit_event(
        session,
        action="SKU_UPDATED",
        entity_type="sku",
        entity_id=str(sku.id),
        actor_user_id=user.id,
        actor_role=actor_role(user),
        old_values=old_values,
        new_values=payload.model_dump(mode="json", exclude_unset=True),
        request_id=request.state.request_id,
    )
    await session.commit()
    return SkuRead.model_validate(sku)


@router.get("/skus/{sku_id}/prices", response_model=list[ProductPriceRead])
async def list_product_prices(
    sku_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[ProductPriceRead]:
    if not is_tcg_user(user):
        raise HTTPException(status_code=403, detail="Internal pricing access is required")
    await get_sku_or_404(session, sku_id)
    rows = list(
        await session.scalars(
            select(ProductPrice)
            .where(ProductPrice.sku_id == sku_id)
            .order_by(ProductPrice.effective_from.desc())
        )
    )
    return [ProductPriceRead.model_validate(row) for row in rows]


@router.post(
    "/skus/{sku_id}/prices",
    response_model=ProductPriceRead,
    status_code=status.HTTP_201_CREATED,
)
async def set_product_price(
    sku_id: UUID,
    payload: ProductPriceCreate,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ProductPriceRead:
    require_tcg_admin(user)
    await get_sku_or_404(session, sku_id)
    price = await session.scalar(
        select(ProductPrice).where(
            ProductPrice.sku_id == sku_id,
            ProductPrice.effective_from == payload.effective_from,
        )
    )
    action = "PRODUCT_PRICE_UPDATED" if price else "PRODUCT_PRICE_CREATED"
    if price is None:
        price = ProductPrice(sku_id=sku_id, **payload.model_dump(), currency="USD")
        session.add(price)
    else:
        price.amount = payload.amount
        price.effective_until = payload.effective_until
        price.is_active = True
    await session.flush()
    await record_audit_event(
        session,
        action=action,
        entity_type="product_price",
        entity_id=str(price.id),
        actor_user_id=user.id,
        actor_role=actor_role(user),
        new_values=payload.model_dump(mode="json") | {"sku_id": str(sku_id), "currency": "USD"},
        request_id=request.state.request_id,
    )
    await session.commit()
    return ProductPriceRead.model_validate(price)


@router.delete("/skus/{sku_id}/prices/{price_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_product_price(
    sku_id: UUID,
    price_id: UUID,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    require_tcg_admin(user)
    price = await session.scalar(
        select(ProductPrice).where(ProductPrice.id == price_id, ProductPrice.sku_id == sku_id)
    )
    if price is None:
        raise HTTPException(status_code=404, detail="Product price not found")
    price.is_active = False
    await record_audit_event(
        session,
        action="PRODUCT_PRICE_DEACTIVATED",
        entity_type="product_price",
        entity_id=str(price.id),
        actor_user_id=user.id,
        actor_role=actor_role(user),
        request_id=request.state.request_id,
    )
    await session.commit()
