"""Unit tests for matcher.py — contractual item detection and batch matching.

Both tested functions are pure (no external dependencies).
"""
import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from services.rag_process.matcher import is_contractual_item, match_boq_items_batch  # noqa: E402


def _item(**kwargs) -> dict:
    base = {"description": "brick masonry wall", "category": "brick_masonry"}
    base.update(kwargs)
    return base


def _mock_match_fn(description: str) -> dict:
    return {
        "item_no": "A1.1",
        "description": "Brick masonry wall",
        "unit": "m2",
        "rate": 2500.0,
        "confidence": 0.85,
        "match_type": "confirmed",
        "needs_rate_review": False,
    }


class TestIsContractualItem:
    def test_preliminary_and_general_category_is_contractual(self):
        assert is_contractual_item({"description": "Site clearance", "category": "preliminary_and_general"})

    def test_performance_security_in_description_is_contractual(self):
        assert is_contractual_item({"description": "Performance security bond", "category": "other"})

    def test_advance_payment_bond_in_description_is_contractual(self):
        assert is_contractual_item({"description": "Advance payment bond", "category": "other"})

    def test_lump_sum_in_description_is_contractual(self):
        assert is_contractual_item({"description": "Lump sum allowance", "category": "finishes"})

    def test_regular_masonry_item_not_contractual(self):
        assert not is_contractual_item(_item())

    def test_regular_concrete_item_not_contractual(self):
        assert not is_contractual_item(_item(description="Reinforced concrete column", category="concrete"))

    def test_empty_description_with_non_contractual_category_not_contractual(self):
        assert not is_contractual_item({"description": "", "category": "masonry"})

    def test_missing_keys_default_to_empty_string(self):
        assert not is_contractual_item({})

    def test_case_insensitive_keyword_match(self):
        assert is_contractual_item({"description": "PERFORMANCE SECURITY", "category": "other"})


class TestMatchBoqItemsBatch:
    def test_regular_item_calls_match_fn(self):
        calls: list[str] = []

        def tracking_fn(desc: str) -> dict:
            calls.append(desc)
            return _mock_match_fn(desc)

        items = [_item(description="brick masonry wall")]
        result = match_boq_items_batch(items, tracking_fn)

        assert len(calls) == 1
        assert calls[0] == "brick masonry wall"

    def test_regular_item_merged_with_bsr_fields(self):
        items = [_item()]
        result = match_boq_items_batch(items, _mock_match_fn)

        assert len(result) == 1
        row = result[0]
        assert row["bsr_item_no"] == "A1.1"
        assert row["unit"] == "m2"
        assert row["rate"] == 2500.0
        assert row["match_confidence"] == 0.85
        assert row["match_type"] == "confirmed"

    def test_contractual_item_skips_match_fn(self):
        calls: list[str] = []

        def tracking_fn(desc: str) -> dict:
            calls.append(desc)
            return _mock_match_fn(desc)

        items = [_item(category="preliminary_and_general", description="Site offices")]
        result = match_boq_items_batch(items, tracking_fn)

        assert calls == []
        assert result[0]["bsr_item_no"] == "CONTRACTUAL"
        assert result[0]["rate"] == 0.0
        assert result[0]["match_type"] == "contractual"
        assert result[0]["needs_rate_review"] is True

    def test_mixed_batch_processes_correctly(self):
        items = [
            _item(description="brick masonry"),
            _item(description="Performance security bond", category="other"),
            _item(description="concrete column"),
        ]
        calls: list[str] = []

        def tracking_fn(desc: str) -> dict:
            calls.append(desc)
            return _mock_match_fn(desc)

        result = match_boq_items_batch(items, tracking_fn)

        assert len(result) == 3
        assert len(calls) == 2  # only non-contractual items call the matcher
        assert result[1]["match_type"] == "contractual"

    def test_empty_batch_returns_empty(self):
        result = match_boq_items_batch([], _mock_match_fn)
        assert result == []

    def test_original_item_fields_preserved_in_merged_result(self):
        items = [_item(description="brick masonry", section="Masonry Works", qty=10.5)]
        result = match_boq_items_batch(items, _mock_match_fn)

        assert result[0]["section"] == "Masonry Works"
        assert result[0]["qty"] == 10.5

    def test_contractual_item_original_fields_preserved(self):
        items = [_item(description="Performance security", category="preliminary_and_general", section="Prelims")]
        result = match_boq_items_batch(items, _mock_match_fn)

        assert result[0]["section"] == "Prelims"
        assert result[0]["bsr_item_no"] == "CONTRACTUAL"
