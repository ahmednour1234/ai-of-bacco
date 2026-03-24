"""
app/ai/pipelines/universal_extraction_pipeline.py
==================================================
The master orchestrator that runs the full 6-stage extraction pipeline:

  Stage 1 (Parse)     → UniversalDocumentParser → DocumentRepresentation
  Stage 2 (Guard)     → Validate representation is non-empty
  Stage 3 (Detect)    → DocumentDetector → DetectionResult
  Stage 4 (Regions)   → RegionDetector   → list[DocumentRegion]
  Stage 5 (Classify)  → RowClassifier    → list[ClassifiedRow]  per region
  Stage 6 (Extract)   → ProductExtractor → list[CandidateData]  per region

Implements the existing BasePipeline interface so it is interchangeable with
any future pipeline implementation.

The run() method accepts a payload dict:
  {
    "file_bytes" : bytes,
    "filename"   : str,
    "correction_examples": list[dict]   (optional — few-shot learning)
  }

Returns an ExtractionPipelineResult encoded as a dict (via .to_dict()).
"""

from __future__ import annotations

import logging
from typing import Any

from app.ai.document_intelligence.document_detector import DocumentDetector
from app.ai.document_intelligence.product_extractor import ProductExtractor
from app.ai.document_intelligence.region_detector import RegionDetector
from app.ai.document_intelligence.row_classifier import RowClassifier
from app.ai.interfaces.base_pipeline import BasePipeline
from app.ai.parsers.universal_document_parser import UniversalDocumentParser
from app.schemas.document_representation import (
    DocumentRegion,
    ExtractionPipelineResult,
)
from app.schemas.extraction import CandidateData

logger = logging.getLogger(__name__)


class UniversalExtractionPipeline(BasePipeline):
    """
    Format-agnostic, LLM-first product extraction pipeline.

    Design principles:
    - Parser layer is format-agnostic; downstream stages only see DocumentRepresentation.
    - LLM is primary for detection, region labelling, row classification, extraction.
    - Heuristics are automatic fallback if LLM is unavailable or fails.
    - All raw LLM responses stored in detection_metadata for auditability.
    - Correction examples are injected as few-shot context to improve extraction.
    """

    def __init__(self) -> None:
        self._parser = UniversalDocumentParser()
        self._detector = DocumentDetector()
        self._region_detector = RegionDetector()
        self._row_classifier = RowClassifier()
        # ProductExtractor is instantiated per run (receives correction_examples)

    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Execute the pipeline.

        payload keys:
          file_bytes          : bytes  (required)
          filename            : str    (required)
          correction_examples : list   (optional)

        Returns a dict representation of ExtractionPipelineResult.
        """
        file_bytes: bytes = payload["file_bytes"]
        filename: str = payload["filename"]
        correction_examples: list[dict] = payload.get("correction_examples", [])

        # ── Stage 1: Parse ───────────────────────────────────────────────────
        logger.info("Pipeline [%s] Stage 1: Parsing document...", filename)
        parse_result = await self._parser.parse(file_bytes, filename)
        doc = parse_result["representation"]

        if not doc.full_text.strip() and not doc.tables:
            logger.warning("Pipeline [%s]: No text or tables extracted.", filename)
            result = ExtractionPipelineResult(
                contains_products=False,
                document_type_guess="unknown",
                detection_confidence=0.0,
                language=doc.language_hint,
                detection_metadata={
                    "parse_warnings": doc.parse_warnings,
                    "reason": "no_text_extracted",
                },
            )
            return _result_to_dict(result)

        # ── Stage 3: Document Detection ──────────────────────────────────────
        logger.info("Pipeline [%s] Stage 3: Detecting document type...", filename)
        detection = await self._detector.detect(doc)
        logger.info(
            "Pipeline [%s] Detection: contains_products=%s type=%s conf=%.2f",
            filename, detection.contains_products,
            detection.document_type_guess, detection.confidence,
        )

        # Accumulate all LLM metadata for auditability
        detection_metadata: dict[str, Any] = {
            "parse_warnings": doc.parse_warnings,
            "detection": detection.metadata,
            "source_format": doc.source_format,
            "page_count": doc.page_count,
        }

        # Early exit if no products
        if not detection.contains_products:
            result = ExtractionPipelineResult(
                contains_products=False,
                document_type_guess=detection.document_type_guess,
                detection_confidence=detection.confidence,
                language=detection.language,
                detection_metadata=detection_metadata,
            )
            return _result_to_dict(result)

        # ── Stage 4: Region Detection ────────────────────────────────────────
        logger.info("Pipeline [%s] Stage 4: Detecting regions...", filename)
        regions = await self._region_detector.detect(doc, detection)

        product_regions: list[DocumentRegion] = [r for r in regions if r.is_product_region]
        ignored_regions: list[DocumentRegion] = [r for r in regions if not r.is_product_region]

        logger.info(
            "Pipeline [%s] Regions: %d product, %d ignored",
            filename, len(product_regions), len(ignored_regions),
        )

        if not product_regions:
            logger.warning(
                "Pipeline [%s]: Detection said contains_products=True but no product regions found.",
                filename,
            )
            # Fall back: treat all non-ignored regions as product regions
            product_regions = [r for r in regions if r.region_type not in (
                "document_header", "totals_block", "payment_info",
                "bank_info", "notes", "ignore",
            )]
            if not product_regions and regions:
                product_regions = [regions[0]]

        # ── Stages 5 + 6: Classify rows & Extract per product region ─────────
        extractor = ProductExtractor(correction_examples=correction_examples)
        all_candidates: list[CandidateData] = []

        for region in product_regions:
            logger.info(
                "Pipeline [%s] Stage 5+6: Classifying & extracting region %s (%s)...",
                filename, region.region_id, region.region_type,
            )
            classified_rows = await self._row_classifier.classify(region)
            region_candidates = await extractor.extract(region, classified_rows)

            # Reassign position to be globally unique
            base_pos = len(all_candidates)
            for i, cand in enumerate(region_candidates):
                cand.position = base_pos + i

            all_candidates.extend(region_candidates)

        # ── Compute overall confidence ────────────────────────────────────────
        overall_confidence = 0.0
        if all_candidates:
            overall_confidence = sum(c.confidence for c in all_candidates) / len(all_candidates)

        logger.info(
            "Pipeline [%s] Complete: %d products extracted, overall_confidence=%.2f",
            filename, len(all_candidates), overall_confidence,
        )

        result = ExtractionPipelineResult(
            contains_products=True,
            document_type_guess=detection.document_type_guess,
            detection_confidence=detection.confidence,
            language=detection.language,
            product_regions=product_regions,
            ignored_regions=ignored_regions,
            candidates=all_candidates,
            overall_confidence=overall_confidence,
            detection_metadata=detection_metadata,
        )
        return _result_to_dict(result)


def _result_to_dict(result: ExtractionPipelineResult) -> dict[str, Any]:
    """
    Serialize the pipeline result to a plain dict.
    CandidateData objects are kept as-is so ExtractionSessionService can
    access them directly without JSON round-tripping.
    """
    return {
        "contains_products": result.contains_products,
        "document_type_guess": result.document_type_guess,
        "detection_confidence": result.detection_confidence,
        "language": result.language,
        "product_regions": result.product_regions,      # list[DocumentRegion]
        "ignored_regions": result.ignored_regions,      # list[DocumentRegion]
        "candidates": result.candidates,                 # list[CandidateData]
        "overall_confidence": result.overall_confidence,
        "detection_metadata": result.detection_metadata,
    }
