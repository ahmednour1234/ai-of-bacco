"""
app/ai/evaluation/benchmark.py
================================
BenchmarkRunner — loads test datasets (JSON / CSV), runs the extraction
pipeline against them, and produces an EvaluationReport.

Dataset formats
---------------
JSON:  list of objects with keys: raw_text, label, product_name?, quantity?,
       unit?, price?, brand?, category?

CSV:   columns: raw_text, label[, product_name, quantity, unit, price, brand, category]

Usage:
    runner = BenchmarkRunner()
    runner.load_json("data/benchmark_en.json")
    runner.load_csv("data/benchmark_ar.csv")
    report = runner.run(service)
    runner.write_report(report, "results/report.json", fmt="json")
    runner.write_report(report, "results/report.csv", fmt="csv")
"""

from __future__ import annotations

import csv
import io
import json
import logging
import pathlib
from typing import Any

from app.ai.evaluation.metrics import (
    EvaluationReport,
    LabeledRow,
    compute_evaluation_report,
)

logger = logging.getLogger(__name__)


class BenchmarkRunner:
    """
    Orchestrates loading test data → running extraction → computing metrics.
    """

    def __init__(self) -> None:
        self._ground_truths: list[LabeledRow] = []

    # ── Loading ────────────────────────────────────────────────────────────────

    def load_json(self, path: str | pathlib.Path) -> None:
        """Append ground-truth rows from a JSON file."""
        data: list[dict[str, Any]] = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        for rec in data:
            self._ground_truths.append(self._dict_to_row(rec))
        logger.info("Loaded %d ground-truth rows from %s", len(data), path)

    def load_csv(self, path: str | pathlib.Path) -> None:
        """Append ground-truth rows from a CSV file."""
        text = pathlib.Path(path).read_text(encoding="utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        count = 0
        for rec in reader:
            self._ground_truths.append(self._dict_to_row(rec))
            count += 1
        logger.info("Loaded %d ground-truth rows from %s", count, path)

    def clear(self) -> None:
        self._ground_truths.clear()

    # ── Running ────────────────────────────────────────────────────────────────

    def run_from_candidates(
        self,
        predictions: list[Any],  # list[CandidateData]
    ) -> EvaluationReport:
        """
        Evaluate against pre-computed CandidateData predictions.
        Each CandidateData is mapped to a LabeledRow.
        """
        pred_rows = [self._candidate_to_row(c) for c in predictions]
        return compute_evaluation_report(pred_rows, self._ground_truths)

    # ── Reporting ──────────────────────────────────────────────────────────────

    def write_report(
        self,
        report: EvaluationReport,
        output_path: str | pathlib.Path,
        fmt: str = "json",
    ) -> None:
        """
        Write the evaluation report to disk.

        Args:
            report:      EvaluationReport from run_from_candidates().
            output_path: Destination file path.
            fmt:         "json" or "csv".
        """
        out = pathlib.Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        if fmt == "json":
            payload = {
                "summary": report.to_dict(),
                "rows": report.row_details,
            }
            out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info("Report written to %s (JSON)", out)

        elif fmt == "csv":
            summary = report.to_dict()
            with out.open("w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                # Summary block
                writer.writerow(["metric", "value"])
                for k, v in summary.items():
                    if isinstance(v, dict):
                        for fk, fv in v.items():
                            writer.writerow([f"field_{fk}", fv])
                    else:
                        writer.writerow([k, v])
                writer.writerow([])
                # Row detail block
                if report.row_details:
                    detail_keys = list(report.row_details[0].keys())
                    writer.writerow(detail_keys)
                    for row in report.row_details:
                        writer.writerow([row.get(k, "") for k in detail_keys])
            logger.info("Report written to %s (CSV)", out)
        else:
            raise ValueError(f"Unsupported format: {fmt!r}. Use 'json' or 'csv'.")

    # ── Internal helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _dict_to_row(rec: dict[str, Any]) -> LabeledRow:
        def _flt(v: Any) -> float | None:
            if v is None or str(v).strip() == "":
                return None
            try:
                return float(str(v).replace(",", ""))
            except ValueError:
                return None

        return LabeledRow(
            raw_text=str(rec.get("raw_text", "")),
            label=str(rec.get("label", "ignore")),
            product_name=rec.get("product_name") or None,
            quantity=_flt(rec.get("quantity")),
            unit=rec.get("unit") or None,
            price=_flt(rec.get("price")),
            brand=rec.get("brand") or None,
            category=rec.get("category") or None,
        )

    @staticmethod
    def _candidate_to_row(cand: Any) -> LabeledRow:
        return LabeledRow(
            raw_text=cand.raw_text,
            label=cand.predicted_label,
            product_name=cand.product_name,
            quantity=cand.quantity,
            unit=cand.unit,
            price=cand.price,
            brand=cand.brand,
            category=cand.category,
        )
