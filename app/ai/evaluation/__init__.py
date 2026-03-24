"""
app/ai/evaluation
=================
Extraction evaluation and benchmarking sub-package.
"""

from .metrics import LabeledRow, EvaluationReport, compute_evaluation_report
from .benchmark import BenchmarkRunner

__all__ = [
    "LabeledRow",
    "EvaluationReport",
    "compute_evaluation_report",
    "BenchmarkRunner",
]
