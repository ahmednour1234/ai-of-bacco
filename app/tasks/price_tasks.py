"""
app/tasks/price_tasks.py
-------------------------
Celery tasks for price estimation and market-data refresh.
"""

from __future__ import annotations

from app.tasks.celery_app import celery_app


@celery_app.task(bind=True, name="tasks.estimate_product_price", max_retries=3)
def estimate_product_price(self, product_id: str, org_id: str) -> dict:
    """
    Run PriceEstimationPipeline for the given product and persist the result.

    TODO: Inject PriceEstimationPipeline + PriceEstimationService.
    """
    try:
        return {
            "product_id": product_id,
            "status": "queued",
            "message": "estimate_product_price stub — pipeline not yet wired.",
        }
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="tasks.refresh_supplier_prices")
def refresh_supplier_prices(org_id: str) -> dict:
    """
    Periodic task: re-check supplier price lists and update SupplierProduct prices.

    TODO: Inject SupplierProductRepository + PriceListParser.
    """
    return {
        "org_id": org_id,
        "status": "queued",
        "message": "refresh_supplier_prices stub — not yet implemented.",
    }
