from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    commercial,
    deals,
    documents,
    health,
    onboarding,
    operations,
    partners,
    pricing,
    products,
    quotes,
    staff,
)

api_router = APIRouter()
api_router.include_router(staff.router, prefix="/staff-users", tags=["staff users"])
api_router.include_router(onboarding.router, prefix="/onboarding", tags=["onboarding"])
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(partners.router, prefix="/partners", tags=["partners"])
api_router.include_router(products.router, prefix="/products", tags=["products"])
api_router.include_router(pricing.router, prefix="/pricing", tags=["pricing"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(deals.router, prefix="/deals", tags=["deals"])
api_router.include_router(quotes.router, prefix="/quotes", tags=["quotes"])
api_router.include_router(operations.maf_router, prefix="/maf", tags=["maf"])
api_router.include_router(operations.orders_router, prefix="/orders", tags=["orders"])

api_router.include_router(commercial.router, prefix="/commercial", tags=["commercial"])
