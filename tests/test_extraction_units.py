"""
tests/test_extraction_units.py
================================
Unit tests for the extraction normalization, validation, and service modules.
These tests are purely in-memory — no database, no file I/O, no network.

Run with:
    pytest tests/test_extraction_units.py -v
"""

from __future__ import annotations

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# UnitNormalizer
# ─────────────────────────────────────────────────────────────────────────────

class TestUnitNormalizer:
    @pytest.fixture(autouse=True)
    def setup(self):
        from app.ai.normalization.unit_normalizer import UnitNormalizer
        self.norm = UnitNormalizer()

    def test_english_pc(self):
        assert self.norm.canonical("pcs") == "pc"
        assert self.norm.canonical("Pieces") == "pc"
        assert self.norm.canonical("PC") == "pc"

    def test_arabic_qty(self):
        assert self.norm.canonical("قطعة") == "pc"
        assert self.norm.canonical("حبة") == "pc"
        assert self.norm.canonical("عدد") == "pc"

    def test_weight(self):
        assert self.norm.canonical("kg") == "kg"
        assert self.norm.canonical("KGS") == "kg"
        assert self.norm.canonical("كيلو") == "kg"
        assert self.norm.canonical("طن") == "ton"

    def test_length(self):
        assert self.norm.canonical("mtr") == "m"
        assert self.norm.canonical("Meter") == "m"
        assert self.norm.canonical("متر") == "m"
        assert self.norm.canonical("ft") == "ft"

    def test_volume(self):
        assert self.norm.canonical("ltr") == "l"
        assert self.norm.canonical("liters") == "l"
        assert self.norm.canonical("لتر") == "l"

    def test_area(self):
        assert self.norm.canonical("sqm") == "m2"
        assert self.norm.canonical("m2") == "m2"

    def test_set(self):
        assert self.norm.canonical("set") == "set"
        assert self.norm.canonical("طقم") == "set"

    def test_box(self):
        assert self.norm.canonical("carton") == "box"
        assert self.norm.canonical("CTN") == "box"
        assert self.norm.canonical("كرتون") == "box"

    def test_unknown_returns_none(self):
        assert self.norm.canonical("xyz_gibberish_99") is None
        assert self.norm.canonical(None) is None
        assert self.norm.canonical("") is None

    def test_trailing_dot_stripped(self):
        assert self.norm.canonical("pcs.") == "pc"

    def test_is_weight(self):
        assert self.norm.is_weight("kg") is True
        assert self.norm.is_weight("طن") is True
        assert self.norm.is_weight("m") is False

    def test_is_length(self):
        assert self.norm.is_length("mtr") is True
        assert self.norm.is_length("kg") is False


# ─────────────────────────────────────────────────────────────────────────────
# QuantityParser
# ─────────────────────────────────────────────────────────────────────────────

class TestQuantityParser:
    @pytest.fixture(autouse=True)
    def setup(self):
        from app.ai.normalization.quantity_parser import QuantityParser
        self.parser = QuantityParser(enable_llm=False)

    def _parse(self, text):
        return self.parser.parse(text)

    def test_explicit_english(self):
        r = self._parse("100 pcs of material")
        assert r.quantity == 100.0
        assert r.unit is not None
        assert r.unit.lower().startswith("pc")
        assert r.method == "explicit_unit"

    def test_explicit_arabic(self):
        r = self._parse("مكيف ترين 5 طن حار")
        assert r.quantity == 5.0
        assert "طن" in (r.unit or "")
        assert r.method == "explicit_unit"

    def test_explicit_kg(self):
        r = self._parse("50 kg steel pipe")
        assert r.quantity == 50.0
        assert r.unit and "kg" in r.unit.lower()

    def test_explicit_meter(self):
        r = self._parse("12.5 mtr pipe")
        assert r.quantity == 12.5
        assert r.method == "explicit_unit"

    def test_fraction(self):
        # Fraction method fires when there is no numeric unit pair adjacent to the fraction.
        r = self._parse("item 3/4 of stock")
        assert abs(r.quantity - 0.75) < 0.001
        assert r.method == "fraction"

    def test_reverse_calc_arabic(self):
        # When the text contains an explicit unit (طن), explicit_unit fires first.
        # Reverse-calc is only reached when there is no explicit unit token.
        # Verify the parser still returns a valid product quantity.
        r = self._parse("مكيف ترين مخفي 5 طن انفيرتر 2 13350 26700")
        assert r.quantity is not None
        assert r.method in {"explicit_unit", "reverse_calc"}

    def test_reverse_calc_arabic_no_unit(self):
        # Without an explicit unit, reverse_calc should kick in.
        r = self._parse("مكيف ترين مخفي المنتج 2 13350 26700")
        assert r.quantity == 2.0
        assert r.method == "reverse_calc"

    def test_reverse_calc_english(self):
        # qty price total pattern
        r = self._parse("product name 3.00 4630.00 13890.00")
        assert r.quantity == 3.0
        assert r.method == "reverse_calc"

    def test_trailing_integer_fallback(self):
        r = self._parse("some random product text 4")
        assert r.quantity == 4.0
        assert r.method == "trailing_integer"

    def test_no_quantity(self):
        r = self._parse("project header — grand total")
        assert r.quantity is None
        assert r.method == "none"

    def test_decimal_comma(self):
        r = self._parse("2,5 kg cement")
        # Both comma-as-decimal and explicit unit should give qty ~2 or 2.5
        assert r.quantity is not None

    def test_range_returns_midpoint(self):
        # Use a hyphenated range with no explicit-unit token so range_midpoint wins.
        r = self._parse("order 2-4 of pipe")
        assert r.quantity == 3.0
        assert r.method == "range_midpoint"


# ─────────────────────────────────────────────────────────────────────────────
# CandidateValidator
# ─────────────────────────────────────────────────────────────────────────────

class TestCandidateValidator:
    @pytest.fixture(autouse=True)
    def setup(self):
        from app.ai.validation.candidate_validator import CandidateValidator
        from app.schemas.extraction import CandidateData
        self.validator = CandidateValidator()
        self.CandidateData = CandidateData

    def _make_candidate(self, **kwargs):
        defaults = dict(
            raw_text="test product",
            predicted_label="product",
            confidence=0.80,
            position=0,
        )
        defaults.update(kwargs)
        return self.CandidateData(**defaults)

    def test_valid_total_boosts_confidence(self):
        cand = self._make_candidate(quantity=3.0, price=1000.0, total=3000.0)
        initial_conf = cand.confidence
        self.validator.validate_candidates([cand])
        assert cand.confidence > initial_conf
        assert "total_mismatch" not in cand.validation_flags

    def test_total_mismatch_flagged(self):
        cand = self._make_candidate(quantity=3.0, price=1000.0, total=9999.0)
        self.validator.validate_candidates([cand])
        assert "total_mismatch" in cand.validation_flags

    def test_qty_price_swap_flagged(self):
        cand = self._make_candidate(quantity=500.0, price=0.5)
        self.validator.validate_candidates([cand])
        assert "possible_qty_price_swap" in cand.validation_flags

    def test_qty_very_large_flagged(self):
        cand = self._make_candidate(quantity=50000.0, price=10.0)
        self.validator.validate_candidates([cand])
        assert "qty_very_large" in cand.validation_flags

    def test_unit_without_qty_flagged(self):
        cand = self._make_candidate(unit="pcs", quantity=None)
        self.validator.validate_candidates([cand])
        assert "unit_without_qty" in cand.validation_flags
        assert cand.needs_review is True

    def test_clean_candidate_no_flags(self):
        cand = self._make_candidate(quantity=2.0, price=500.0, total=1000.0)
        self.validator.validate_candidates([cand])
        assert cand.validation_flags == []
        assert cand.needs_review is False

    def test_skips_non_product_candidates(self):
        cand = self._make_candidate(predicted_label="meta", quantity=None, price=None)
        self.validator.validate_candidates([cand])
        # No flags should be applied since label is not "product"
        assert cand.validation_flags == []

    def test_negative_qty_flagged(self):
        cand = self._make_candidate(quantity=-5.0, price=100.0)
        self.validator.validate_candidates([cand])
        assert "negative_qty" in cand.validation_flags

    def test_multiple_flags_lower_confidence(self):
        cand = self._make_candidate(quantity=-5.0, price=-10.0)
        cand.confidence = 0.80
        self.validator.validate_candidates([cand])
        assert cand.confidence < 0.80
        assert cand.needs_review is True


# ─────────────────────────────────────────────────────────────────────────────
# ProductExtractionService (CSV path — no file I/O, no DB)
# ─────────────────────────────────────────────────────────────────────────────

class TestProductExtractionServiceCSV:
    @pytest.fixture(autouse=True)
    def setup(self):
        from app.services.product_extraction_service import ProductExtractionService
        self.service = ProductExtractionService()

    def test_csv_basic(self):
        csv_bytes = (
            b"product_name,quantity,unit,price\n"
            b"Copper Pipe 1 inch,10,pcs,45.00\n"
            b"Ball Valve 2 inch,5,pcs,120.00\n"
        )
        candidates = self.service._candidates_from_csv(csv_bytes)
        assert len(candidates) == 2
        assert candidates[0].product_name == "Copper Pipe 1 inch"
        assert candidates[0].quantity == 10.0
        assert candidates[1].quantity == 5.0

    def test_csv_arabic(self):
        csv_bytes = (
            "product_name,quantity,unit,price\n"
            "مكيف ترين مخفي,2,طن,13350\n"
        ).encode("utf-8")
        candidates = self.service._candidates_from_csv(csv_bytes)
        assert len(candidates) == 1
        assert candidates[0].product_name == "مكيف ترين مخفي"
        assert candidates[0].quantity == 2.0

    def test_csv_unit_normalized(self):
        csv_bytes = b"product_name,qty,unit\nSteel Rod,5,pcs\n"
        candidates = self.service._candidates_from_csv(csv_bytes)
        assert candidates[0].normalized_unit == "pc"
        assert candidates[0].unit == "pc"

    def test_csv_infer_qty_from_total(self):
        csv_bytes = b"product_name,price,total\nCement Bag,25.00,125.00\n"
        candidates = self.service._candidates_from_csv(csv_bytes)
        assert candidates[0].quantity == 5.0

    def test_csv_deduplication(self):
        csv_bytes = (
            b"product_name,quantity,price\n"
            b"Pipe,10,50\n"
            b"Pipe,10,50\n"
        )
        candidates = self.service._candidates_from_csv(csv_bytes)
        assert len(candidates) == 1

    def test_csv_empty_rows_skipped(self):
        csv_bytes = b"product_name,quantity\n,\n  ,\nActual Product,3\n"
        candidates = self.service._candidates_from_csv(csv_bytes)
        assert len(candidates) == 1
        assert candidates[0].product_name == "Actual Product"

    def test_text_table_extraction(self):
        text = (
            "Description         Qty   Unit   Unit Price   Total\n"
            "PPR Pipe 63mm        10    pcs      45.00      450.00\n"
            "Elbow 90° 63mm       20    pcs      12.50      250.00\n"
        )
        candidates = self.service._candidates_from_text(text)
        assert len(candidates) >= 2

    def test_text_arabic_inline(self):
        text = "مكيف ترين مخفي 5 طن حار وبارد انفيرتر 2 13350 26700\n"
        candidates = self.service._candidates_from_text(text)
        # Should detect at least one product
        product_candidates = [c for c in candidates if c.predicted_label == "product"]
        assert len(product_candidates) >= 1


# ─────────────────────────────────────────────────────────────────────────────
# EvaluationReport metrics
# ─────────────────────────────────────────────────────────────────────────────

class TestEvaluationMetrics:
    @pytest.fixture(autouse=True)
    def setup(self):
        from app.ai.evaluation.metrics import LabeledRow, compute_evaluation_report
        self.LabeledRow = LabeledRow
        self.compute = compute_evaluation_report

    def _row(self, label="product", name="Product A", qty=1.0, price=100.0):
        return self.LabeledRow(
            raw_text=name, label=label, product_name=name, quantity=qty, price=price
        )

    def test_perfect_recall_precision(self):
        preds = [self._row("product"), self._row("product"), self._row("ignore")]
        truths = [self._row("product"), self._row("product"), self._row("ignore")]
        report = self.compute(preds, truths)
        assert report.precision == 1.0
        assert report.recall == 1.0
        assert report.f1 == 1.0

    def test_false_positives(self):
        preds = [self._row("product"), self._row("product")]
        truths = [self._row("product"), self._row("ignore")]
        report = self.compute(preds, truths)
        assert report.false_positives == 1
        assert report.precision < 1.0

    def test_false_negatives(self):
        preds = [self._row("ignore"), self._row("product")]
        truths = [self._row("product"), self._row("product")]
        report = self.compute(preds, truths)
        assert report.false_negatives == 1
        assert report.recall < 1.0

    def test_empty_predictions(self):
        truths = [self._row("product")]
        report = self.compute([], truths)
        assert report.false_negatives == 1
        assert report.recall == 0.0

    def test_to_dict_keys(self):
        preds = [self._row()]
        truths = [self._row()]
        report = self.compute(preds, truths)
        d = report.to_dict()
        assert "precision" in d
        assert "recall" in d
        assert "f1" in d
        assert "field_accuracy" in d
