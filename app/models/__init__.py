"""
Models package
==============
Import all models here so Alembic's env.py discovers them
when it imports Base.metadata.
"""

from app.models.organization import Organization
from app.models.user import User
from app.models.uploaded_file import UploadedFile
from app.models.document import Document
from app.models.product import Product
from app.models.product_alias import ProductAlias
from app.models.supplier import Supplier
from app.models.supplier_product import SupplierProduct
from app.models.invoice import Invoice
from app.models.invoice_item import InvoiceItem
from app.models.extracted_item import ExtractedItem
from app.models.price_estimation import PriceEstimation
from app.models.ai_job import AIJob
from app.models.extraction_session import ExtractionSession
from app.models.extraction_candidate import ExtractionCandidate
from app.models.learned_rule import LearnedRule
from app.models.correction_example import CorrectionExample
from app.models.extraction_feedback_event import ExtractionFeedbackEvent

__all__ = [
    "Organization",
    "User",
    "UploadedFile",
    "Document",
    "Product",
    "ProductAlias",
    "Supplier",
    "SupplierProduct",
    "Invoice",
    "InvoiceItem",
    "ExtractedItem",
    "PriceEstimation",
    "AIJob",
    "ExtractionSession",
    "ExtractionCandidate",
    "LearnedRule",
    "CorrectionExample",
    "ExtractionFeedbackEvent",
]
