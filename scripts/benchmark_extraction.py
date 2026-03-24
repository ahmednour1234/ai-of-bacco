"""
scripts/benchmark_extraction.py
=================================
CLI entry point for running the extraction pipeline against a benchmark dataset
and producing precision/recall/F1 metrics.

Usage:
    python scripts/benchmark_extraction.py \\
        --input-dir  data/benchmark/docs \\
        --ground-truth data/benchmark/labels.json \\
        --output results/report \\
        --format json

    # Or using a CSV ground-truth file:
    python scripts/benchmark_extraction.py \\
        --ground-truth data/labels.csv \\
        --output results/report \\
        --format csv

Arguments:
    --ground-truth  Path to JSON or CSV ground-truth file (required).
    --input-dir     Directory of raw documents to extract from (optional).
                    If omitted, extraction is skipped and the report is
                    computed against the ground-truth labels only (useful
                    for debugging the metric pipeline).
    --output        Output path prefix (extension added from --format).
    --format        "json" or "csv" (default: json).
    --no-llm        Disable LLM fallback in QuantityParser (default: LLM off).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import pathlib
import sys

# Ensure project root is on sys.path when run directly
_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Must set before any SQLAlchemy import (antivirus workaround for Windows)
os.environ.setdefault("DISABLE_SQLALCHEMY_CEXT_RUNTIME", "1")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("benchmark")


async def _run(args: argparse.Namespace) -> None:
    from app.ai.evaluation.benchmark import BenchmarkRunner

    runner = BenchmarkRunner()

    # ── Load ground truth ──────────────────────────────────────────────────────
    gt_path = pathlib.Path(args.ground_truth)
    if not gt_path.exists():
        logger.error("Ground-truth file not found: %s", gt_path)
        sys.exit(1)

    if gt_path.suffix.lower() == ".csv":
        runner.load_csv(gt_path)
    else:
        runner.load_json(gt_path)

    # ── Extract from input documents (optional) ────────────────────────────────
    predictions = []
    if args.input_dir:
        input_dir = pathlib.Path(args.input_dir)
        if not input_dir.exists():
            logger.error("Input directory not found: %s", input_dir)
            sys.exit(1)

        from fastapi import UploadFile
        from app.services.product_extraction_service import ProductExtractionService
        import io

        service = ProductExtractionService(enable_llm_qty=not args.no_llm)
        supported = {".pdf", ".csv", ".xlsx", ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}

        doc_files = [f for f in input_dir.iterdir() if f.suffix.lower() in supported]
        if not doc_files:
            logger.warning("No supported files found in %s", input_dir)

        for doc_path in sorted(doc_files):
            logger.info("Processing %s …", doc_path.name)
            file_bytes = doc_path.read_bytes()
            # Wrap in a minimal UploadFile-compatible object
            upload = UploadFile(
                filename=doc_path.name,
                file=io.BytesIO(file_bytes),
            )
            try:
                candidates = await service.extract_candidates(upload)
                predictions.extend(candidates)
                logger.info("  → %d candidates", len(candidates))
            except Exception as exc:
                logger.error("  ! Failed to process %s: %s", doc_path.name, exc)

        logger.info("Total predictions: %d", len(predictions))
    else:
        logger.info("--input-dir not provided, using ground-truth as predictions (self-eval).")
        from app.ai.evaluation.metrics import LabeledRow
        # Use ground-truth rows as predictions → perfect scores (sanity check)
        predictions = runner._ground_truths  # type: ignore[attr-defined]

    # ── Evaluate ───────────────────────────────────────────────────────────────
    report = runner.run_from_candidates(predictions)

    summary = report.to_dict()
    logger.info("Results:")
    logger.info("  Precision : %.4f", summary["precision"])
    logger.info("  Recall    : %.4f", summary["recall"])
    logger.info("  F1        : %.4f", summary["f1"])
    logger.info("  TP=%d  FP=%d  FN=%d  TN=%d",
                summary["true_positives"], summary["false_positives"],
                summary["false_negatives"], summary["true_negatives"])
    if summary.get("field_accuracy"):
        logger.info("  Field accuracy:")
        for field, acc in summary["field_accuracy"].items():
            logger.info("    %-20s %.4f", field, acc)

    # ── Write report ───────────────────────────────────────────────────────────
    output_path = pathlib.Path(args.output).with_suffix(f".{args.format}")
    runner.write_report(report, output_path, fmt=args.format)
    logger.info("Report saved to %s", output_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark the extraction pipeline against labeled ground-truth data."
    )
    parser.add_argument(
        "--ground-truth",
        required=True,
        help="Path to the ground-truth file (JSON or CSV).",
    )
    parser.add_argument(
        "--input-dir",
        default=None,
        help="Directory of source documents to extract from. If omitted, self-evaluation mode.",
    )
    parser.add_argument(
        "--output",
        default="benchmark_report",
        help="Output file path prefix (default: benchmark_report).",
    )
    parser.add_argument(
        "--format",
        choices=["json", "csv"],
        default="json",
        help="Output format (default: json).",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        default=True,
        help="Disable LLM fallback in QuantityParser (default: disabled).",
    )

    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
