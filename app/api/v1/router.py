"""
app/api/v1/router.py
---------------------
Central v1 API router — aggregates all domain routers.
Equivalent to Laravel's routes/api.php route group.
"""

from fastapi import APIRouter

from app.api.v1 import (
    users,
    uploaded_files,
    product_extraction,
    extraction,
    documents,
    products,
    suppliers,
    invoices,
    price_estimations,
    ai_jobs,
)

v1_router = APIRouter(prefix="/v1")

v1_router.include_router(users.router)
v1_router.include_router(uploaded_files.router)
v1_router.include_router(product_extraction.router)
v1_router.include_router(extraction.router)
v1_router.include_router(documents.router)
v1_router.include_router(products.router)
v1_router.include_router(suppliers.router)
v1_router.include_router(invoices.router)
v1_router.include_router(price_estimations.router)
v1_router.include_router(ai_jobs.router)
