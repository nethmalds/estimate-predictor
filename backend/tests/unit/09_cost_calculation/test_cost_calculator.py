"""Unit tests for calculate_costs in cost_calculator.py.

Covers:
- BE-TC-043: total = base_total + preliminaries + contingencies
- BE-TC-044: subtotals provided per section / category
- BE-TC-045: zero-quantity item contributes zero cost
"""
import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

# Env vars must be set before importing settings-dependent modules
import os
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("POSTGRES_DB", "testdb")
os.environ.setdefault("ENV", "development")

from services.pricing_process.cost_calculator import calculate_costs  # noqa: E402


def _item(desc: str, category: str, rate: float, quantity: float, **extra) -> dict:
    return {"description": desc, "category": category, "rate": rate, "quantity": quantity, **extra}


# ── BE-TC-043: total = base + preliminaries + contingencies ───────────────────

class TestTotalComposition:
    def test_total_equals_sum_of_components(self):
        items = [_item("Brick wall", "brick_masonry", 2500.0, 10.0)]
        result = calculate_costs(items, preliminaries_rate=0.08, contingencies_rate=0.05)

        base = 2500.0 * 10.0
        expected = round(base + base * 0.08 + base * 0.05, 2)
        assert result["total"] == expected

    def test_result_has_all_required_keys(self):
        items = [_item("Concrete beam", "concrete_works", 5000.0, 2.0)]
        result = calculate_costs(items)
        for key in ("base_total", "preliminaries", "contingencies", "total", "subtotals", "items"):
            assert key in result

    def test_base_total_excludes_prelim_and_contingencies(self):
        items = [_item("Brick wall", "brick_masonry", 2000.0, 5.0)]
        result = calculate_costs(items, preliminaries_rate=0.10, contingencies_rate=0.05)
        assert result["base_total"] == pytest.approx(10000.0)

    def test_grand_total_consistency_no_warnings(self):
        items = [_item("Plastering", "plastering_and_rendering", 1200.0, 8.0)]
        result = calculate_costs(items, preliminaries_rate=0.08, contingencies_rate=0.05)
        assert result["consistency_warnings"] == []

    def test_total_is_positive_for_priced_boq(self):
        items = [
            _item("Excavation", "excavation_and_earthwork", 800.0, 20.0),
            _item("Concrete slab", "concrete_works", 4500.0, 10.0),
        ]
        result = calculate_costs(items)
        assert result["total"] > 0


# ── BE-TC-044: subtotals provided per section ─────────────────────────────────

class TestSubtotalsPerSection:
    def test_subtotals_keyed_by_category(self):
        items = [
            _item("Brick wall", "brick_masonry", 2500.0, 4.0),
            _item("Concrete beam", "concrete_works", 5000.0, 2.0),
        ]
        result = calculate_costs(items)
        assert "brick_masonry" in result["subtotals"]
        assert "concrete_works" in result["subtotals"]

    def test_subtotal_values_correct(self):
        items = [
            _item("Brick wall", "brick_masonry", 2500.0, 4.0),
            _item("Concrete beam", "concrete_works", 5000.0, 2.0),
        ]
        result = calculate_costs(items)
        assert result["subtotals"]["brick_masonry"] == pytest.approx(10000.0)
        assert result["subtotals"]["concrete_works"] == pytest.approx(10000.0)

    def test_single_category_single_subtotal(self):
        items = [_item("Painting", "painting_and_finishes", 900.0, 15.0)]
        result = calculate_costs(items)
        assert len(result["subtotals"]) == 1
        assert result["subtotals"]["painting_and_finishes"] == pytest.approx(13500.0)

    def test_multiple_items_same_category_accumulated(self):
        items = [
            _item("Ground floor slab", "concrete_works", 4000.0, 3.0),
            _item("First floor slab", "concrete_works", 4500.0, 2.0),
        ]
        result = calculate_costs(items)
        assert result["subtotals"]["concrete_works"] == pytest.approx(12000.0 + 9000.0)

    def test_base_total_equals_sum_of_subtotals(self):
        items = [
            _item("Brick wall", "brick_masonry", 2500.0, 4.0),
            _item("Concrete", "concrete_works", 5000.0, 2.0),
            _item("Excavation", "excavation_and_earthwork", 800.0, 10.0),
        ]
        result = calculate_costs(items)
        assert result["base_total"] == pytest.approx(sum(result["subtotals"].values()))


# ── BE-TC-045: zero-quantity item contributes zero cost ───────────────────────

class TestZeroQuantityItem:
    def test_zero_quantity_item_has_zero_cost(self):
        items = [_item("Brick wall", "brick_masonry", 2500.0, 0.0)]
        result = calculate_costs(items)
        assert result["items"][0]["cost"] == 0.0

    def test_zero_quantity_does_not_inflate_base_total(self):
        items = [
            _item("Brick wall", "brick_masonry", 2500.0, 0.0),
            _item("Concrete", "concrete_works", 5000.0, 2.0),
        ]
        result = calculate_costs(items)
        assert result["base_total"] == pytest.approx(10000.0)

    def test_zero_rate_item_also_has_zero_cost(self):
        items = [_item("Preliminaries", "preliminary_and_general", 0.0, 1.0)]
        result = calculate_costs(items)
        assert result["items"][0]["cost"] == 0.0

    def test_mixed_items_only_priced_items_sum(self):
        items = [
            _item("Brick wall", "brick_masonry", 2500.0, 0.0),
            _item("Painting", "painting_and_finishes", 900.0, 10.0),
        ]
        result = calculate_costs(items)
        assert result["base_total"] == pytest.approx(9000.0)
