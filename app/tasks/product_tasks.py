"""
app/tasks/product_tasks.py
----------------------------
Celery tasks for product operations (embedding generation, catalog sync …).
"""

from __future__ import annotations

from app.tasks.celery_app import celery_app


@celery_app.task(bind=True, name="tasks.generate_product_embeddings", max_retries=3)
def generate_product_embeddings(self, product_id: str, org_id: str) -> dict:
    """
    Generate and persist vector embeddings for a product and its aliases.

    TODO: Inject BaseEmbedder + ProductAliasRepository.
    """
    try:
        return {
            "product_id": product_id,
            "status": "queued",
            "message": "generate_product_embeddings stub — embedder not yet wired.",
        }
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, name="tasks.match_extracted_items", max_retries=3)
def match_extracted_items(self, document_id: str, org_id: str) -> dict:
    """
    Run ProductMatchingPipeline for all unmatched ExtractedItems
    belonging to the given document.

    TODO: Inject ProductMatchingPipeline + ExtractedItemRepository.
    """
    try:
        return {
            "document_id": document_id,
            "status": "queued",
            "message": "match_extracted_items stub — pipeline not yet wired.",
        }
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)
