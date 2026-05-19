"""Unit tests for validate_quantities in services/validation/quantity_validator.py.

Covers:
- BE-TC-042: anomalous (negative / zero) quantities are flagged in validation
"""
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from services.validation.quantity_validator import validate_quantities  # noqa: E402


def _item(desc: str, quantity: float, rate: float = 2000.0,
          category: str = "brick_masonry", is_contractual: bool = False, **extra) -> dict:
    return {
        "description": desc,
        "quantity": quantity,
        "rate": rate,
        "category": category,
        "is_contractual": is_contractual,
        **extra,
    }


# ── BE-TC-042: anomalous quantities are flagged ───────────────────────────────

class TestNegativeQuantityFlagged:
    def test_negative_quantity_produces_warning(self):
        result = validate_quantities([_item("Brick wall", quantity=-5.0)])
        assert not result["is_valid"]
        assert any("Non-positive" in w for w in result["warnings"])

    def test_zero_quantity_produces_warning(self):
        result = validate_quantities([_item("Concrete beam", quantity=0.0)])
        assert not result["is_valid"]
        assert any("Non-positive" in w for w in result["warnings"])

    def test_positive_quantity_passes(self):
        result = validate_quantities([_item("Plastering", quantity=25.0)])
        # Only check quantity-related validity (rate is non-zero so no rate warning)
        quantity_warnings = [w for w in result["warnings"] if "Non-positive" in w]
        assert len(quantity_warnings) == 0

    def test_multiple_items_each_flagged_separately(self):
        items = [
            _item("Brick wall", quantity=-5.0),
            _item("Concrete", quantity=-1.0),
        ]
        result = validate_quantities(items)
        non_positive = [w for w in result["warnings"] if "Non-positive" in w]
        assert len(non_positive) == 2


class TestZeroRateFlagged:
    def test_zero_rate_on_non_contractual_flagged(self):
        result = validate_quantities([_item("Excavation", quantity=10.0, rate=0.0)])
        assert any("Rate is 0" in w for w in result["warnings"])
        assert "Excavation" in result["missing_rate_items"]

    def test_zero_rate_on_contractual_not_flagged(self):
        result = validate_quantities([
            _item("Preliminaries", quantity=1.0, rate=0.0, is_contractual=True)
        ])
        rate_warnings = [w for w in result["warnings"] if "Rate is 0" in w]
        assert len(rate_warnings) == 0

    def test_non_zero_rate_on_non_contractual_not_flagged(self):
        result = validate_quantities([_item("Painting", quantity=10.0, rate=900.0)])
        rate_warnings = [w for w in result["warnings"] if "Rate is 0" in w]
        assert len(rate_warnings) == 0


class TestCategoryUpperBound:
    def test_suspiciously_large_concrete_quantity_flagged(self):
        # concrete_works upper bound is 5000 m³
        result = validate_quantities([
            _item("Concrete slab", quantity=6000.0, rate=5000.0,
                  category="concrete_works")
        ])
        large_warnings = [w for w in result["warnings"] if "Suspiciously large" in w]
        assert len(large_warnings) == 1

    def test_quantity_within_bounds_not_flagged(self):
        result = validate_quantities([
            _item("Concrete slab", quantity=100.0, rate=5000.0,
                  category="concrete_works")
        ])
        large_warnings = [w for w in result["warnings"] if "Suspiciously large" in w]
        assert len(large_warnings) == 0


class TestIsValidFlag:
    def test_all_valid_items_is_valid_true(self):
        items = [_item("Painting", quantity=20.0, rate=900.0)]
        result = validate_quantities(items)
        assert result["is_valid"] is True

    def test_any_warning_sets_is_valid_false(self):
        items = [_item("Brick wall", quantity=-5.0, rate=2500.0)]
        result = validate_quantities(items)
        assert result["is_valid"] is False

    def test_empty_item_list_is_valid(self):
        result = validate_quantities([])
        assert result["is_valid"] is True
        assert result["warnings"] == []


class TestRateReviewItems:
    def test_needs_rate_review_item_captured(self):
        items = [_item("Special item", quantity=5.0, rate=100.0, needs_rate_review=True)]
        result = validate_quantities(items)
        assert "Special item" in result["rate_review_items"]

    def test_item_without_flag_not_in_review_list(self):
        items = [_item("Normal item", quantity=5.0, rate=2000.0)]
        result = validate_quantities(items)
        assert "Normal item" not in result["rate_review_items"]
