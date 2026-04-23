"""
app/ai/evaluation/metrics.py
=============================
Precision / recall / F1 and field-level accuracy metrics for the extraction pipeline.

Usage:
    report = compute_evaluation_report(predictions, ground_truths)
    print(report.to_dict())
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Any


# ─────────────────────────────────────────────────────────────────────────────
# Data containers
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class LabeledRow:
    """
    A single row with ground-truth and optionally a predicted label/fields.
    Used both as ground-truth input and as a prediction result container.
    """
    raw_text: str
    label: str                   # product | ignore | meta | total | …
    product_name: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    price: Optional[float] = None
    brand: Optional[str] = None
    category: Optional[str] = None


@dataclass
class EvaluationReport:
    """Aggregated evaluation metrics."""

    # Label classification metrics
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    true_negatives: int = 0

    # Field-level accuracy on TP rows (product rows correctly classified)
    field_accuracy: dict[str, float] = field(default_factory=dict)

    # Per-row detail (for debugging)
    row_details: list[dict[str, Any]] = field(default_factory=list)

    @property
    def precision(self) -> float:
        denom = self.true_positives + self.false_positives
        return self.true_positives / denom if denom else 0.0

    @property
    def recall(self) -> float:
        denom = self.true_positives + self.false_negatives
        return self.true_positives / denom if denom else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "true_negatives": self.true_negatives,
            "field_accuracy": {k: round(v, 4) for k, v in self.field_accuracy.items()},
        }


# ─────────────────────────────────────────────────────────────────────────────
# Computation
# ─────────────────────────────────────────────────────────────────────────────

_PRODUCT_LABEL = "product"
_NUMERIC_FIELDS = {"quantity", "price"}
_TEXT_FIELDS = {"product_name", "unit", "brand", "category"}


def _labels_match(pred: str, truth: str) -> bool:
    return pred.lower() == truth.lower()


def _name_match(pred: Optional[str], truth: Optional[str], min_overlap: float = 0.50) -> bool:
    """Fuzzy name match: Jaccard token overlap >= min_overlap."""
    if pred is None or truth is None:
        return pred == truth
    pred_toks = set(pred.lower().split())
    truth_toks = set(truth.lower().split())
    if not truth_toks:
        return False
    overlap = pred_toks & truth_toks
    return len(overlap) / len(truth_toks) >= min_overlap


def _numeric_match(pred: Optional[float], truth: Optional[float], rel_tol: float = 0.05) -> bool:
    if pred is None or truth is None:
        return pred == truth
    if truth == 0:
        return abs(pred) < 1e-6
    return abs(pred - truth) / abs(truth) <= rel_tol


def _text_exact(pred: Optional[str], truth: Optional[str]) -> bool:
    if pred is None and truth is None:
        return True
    if pred is None or truth is None:
        return False
    return pred.strip().lower() == truth.strip().lower()


def compute_evaluation_report(
    predictions: list[LabeledRow],
    ground_truths: list[LabeledRow],
) -> EvaluationReport:
    """
    Compute evaluation metrics by aligning predictions to ground-truths by position.

    Args:
        predictions:   Ordered list of predicted rows (from extraction pipeline).
        ground_truths: Ordered list of ground-truth rows (from benchmark dataset).

    Returns:
        EvaluationReport with precision/recall/F1 and per-field accuracy.
    """
    report = EvaluationReport()
    field_hits: dict[str, int] = {f: 0 for f in [*_TEXT_FIELDS, "product_name"]}
    field_total: dict[str, int] = {f: 0 for f in field_hits}

    n = min(len(predictions), len(ground_truths))

    for i in range(n):
        pred = predictions[i]
        truth = ground_truths[i]

        pred_is_product = _labels_match(pred.label, _PRODUCT_LABEL)
        truth_is_product = _labels_match(truth.label, _PRODUCT_LABEL)

        if pred_is_product and truth_is_product:
            report.true_positives += 1
            detail = {"index": i, "result": "TP", "raw": truth.raw_text}

            # field-level accuracy on TPs
            for f in _TEXT_FIELDS:
                truth_val = getattr(truth, f)
                pred_val = getattr(pred, f)
                if truth_val is not None:
                    field_total[f] += 1
                    if f == "product_name":
                        hit = _name_match(pred_val, truth_val)
                    else:
                        hit = _text_exact(pred_val, truth_val)
                    if hit:
                        field_hits[f] += 1
                    detail[f"field_{f}"] = "ok" if hit else "miss"

            for f in _NUMERIC_FIELDS:
                truth_val = getattr(truth, f)
                pred_val = getattr(pred, f)
                if truth_val is not None:
                    field_total[f] = field_total.get(f, 0) + 1
                    hit = _numeric_match(pred_val, truth_val)
                    if hit:
                        field_hits[f] = field_hits.get(f, 0) + hit
                    detail[f"field_{f}"] = "ok" if hit else "miss"

            report.row_details.append(detail)

        elif pred_is_product and not truth_is_product:
            report.false_positives += 1
            report.row_details.append({"index": i, "result": "FP", "raw": truth.raw_text})

        elif not pred_is_product and truth_is_product:
            report.false_negatives += 1
            report.row_details.append({"index": i, "result": "FN", "raw": truth.raw_text})

        else:
            report.true_negatives += 1

    # Account for length mismatch
    for i in range(n, len(ground_truths)):
        if _labels_match(ground_truths[i].label, _PRODUCT_LABEL):
            report.false_negatives += 1

    for i in range(n, len(predictions)):
        if _labels_match(predictions[i].label, _PRODUCT_LABEL):
            report.false_positives += 1

    # Compute per-field accuracy
    for f in {**field_hits}:
        total = field_total.get(f, 0)
        report.field_accuracy[f] = field_hits[f] / total if total else 0.0

    return report
