"""Unit tests for Tier-2 category-level ML prediction and item distribution.

Covers:
- predict_category_total handles unknown slugs without raising
- distribute_category_to_items splits totals proportionally by QS weight
- Floor-area distribution when per_floor_area_m2 is present in geometry
- Equal split fallback when neither floor nor description vary
- Service-level cascade fires for items that went through global ML allocation
- Cascade silently passes through on prediction failure
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


class TestPredictCategoryTotal:
    def test_unknown_slug_returns_zero_without_raising(self):
        from services.quantity_gen_process.quantity_calculator import predict_category_total
        out = predict_category_total("does_not_exist", {"parameters": {"built_up_area": "1800 sqft"}})
        assert out["is_category_level"] is True
        assert out["category_total"] >= 0.0
        assert 0.0 <= out["confidence"] <= 0.75

    def test_confidence_capped_at_global_scope(self):
        from services.quantity_gen_process.quantity_calculator import predict_category_total
        out = predict_category_total(
            "masonry",
            {"building_type": "residential", "floors": 2,
             "parameters": {"built_up_area": "1800 sqft", "finish_level": "standard"}},
        )
        assert out["confidence"] <= 0.75


class TestDistributionWeights:
    def test_equal_split_when_nothing_varies(self):
        from services.quantity_gen_process.quantity_calculator import (
            distribute_category_to_items,
        )
        items = [
            {"category": "brick_masonry", "description": "Brick wall 225mm", "floor_scope": "all"},
            {"category": "brick_masonry", "description": "Brick wall 225mm", "floor_scope": "all"},
        ]
        out = distribute_category_to_items(100.0, 0.6, items)
        assert out[0]["quantity_allocation_method"] == "equal_split"
        assert out[0]["quantity"] == pytest.approx(50.0)
        assert out[1]["quantity"] == pytest.approx(50.0)
        assert out[0]["quantity_source"] == "category_distributed"

    def test_qs_weight_distribution_when_descriptions_vary(self):
        from services.quantity_gen_process.quantity_calculator import (
            distribute_category_to_items,
        )
        # In brick_masonry: keyword "9" → 70, "4.5" → 30 (per QS rules)
        items = [
            {"category": "brick_masonry", "description": "9 inch external brick wall"},
            {"category": "brick_masonry", "description": "4.5 inch internal brick partition"},
        ]
        out = distribute_category_to_items(100.0, 0.6, items)
        assert out[0]["quantity_allocation_method"] == "qs_weight"
        # 70/100 vs 30/100
        assert out[0]["quantity"] > out[1]["quantity"]
        assert out[0]["quantity"] + out[1]["quantity"] == pytest.approx(100.0, abs=0.01)

    def test_per_floor_area_distribution(self):
        from services.quantity_gen_process.quantity_calculator import (
            distribute_category_to_items,
        )
        items = [
            {"category": "brick_masonry", "description": "Brick wall", "floor_scope": "ground"},
            {"category": "brick_masonry", "description": "Brick wall", "floor_scope": "first"},
        ]
        geometry = {"per_floor_area_m2": {"ground": 100.0, "first": 50.0}}
        out = distribute_category_to_items(150.0, 0.6, items, geometry)
        assert out[0]["quantity_allocation_method"] == "per_floor_area"
        assert out[0]["quantity"] == pytest.approx(100.0, abs=0.01)
        assert out[1]["quantity"] == pytest.approx(50.0, abs=0.01)

    def test_distribute_does_not_mutate_originals(self):
        from services.quantity_gen_process.quantity_calculator import (
            distribute_category_to_items,
        )
        items = [
            {"category": "brick_masonry", "description": "Brick wall A"},
            {"category": "brick_masonry", "description": "Brick wall B"},
        ]
        before = [dict(it) for it in items]
        distribute_category_to_items(100.0, 0.6, items)
        assert items == before


class TestServiceTier2Cascade:
    def test_cascade_overrides_global_allocation(self):
        """When predict_category_total returns a non-zero total, items end up
        tagged with quantity_source = 'category_distributed'."""
        from services.quantity_gen_process import service as svc

        items = [
            {"category": "brick_masonry", "description": "9 inch external brick wall",
             "unit": "m²", "floor_scope": "all"},
            {"category": "brick_masonry", "description": "4.5 inch internal partition",
             "unit": "m²", "floor_scope": "all"},
        ]
        project_info = {
            "building_type": "residential",
            "floors": 1,
            "parameters": {"built_up_area": "120 m²", "finish_level": "standard"},
        }

        # Force item-level ML to be unavailable (global path) and patch the
        # Tier-2 prediction to return a known total.
        with patch.object(svc, "predict_quantity",
                          return_value={"quantity": 10.0, "method": "quantity_predictor",
                                        "is_item_level": False, "model_scope": "global",
                                        "prediction_confidence": 0.5,
                                        "feature_completeness": 0.7,
                                        "unknown_feature_count": 0,
                                        "unknown_feature_names": [],
                                        "allocation_mode": "direct"}), \
             patch.object(svc, "predict_category_total",
                          return_value={"category_total": 80.0, "confidence": 0.6,
                                        "is_category_level": True, "unit": "m²"}):
            result = svc.compute_quantities(items, project_info, floorplan_geometry=None)

        sources = {it.get("quantity_source") for it in result}
        assert "category_distributed" in sources
        # The two items should sum to ~80 (with QS-weight split between 9" and 4.5")
        total = sum(it["quantity"] for it in result)
        assert total == pytest.approx(80.0, abs=0.5)

    def test_cascade_silently_falls_through_on_failure(self):
        from services.quantity_gen_process import service as svc

        items = [
            {"category": "brick_masonry", "description": "9 inch external brick wall",
             "unit": "m²", "floor_scope": "all"},
        ]
        project_info = {
            "building_type": "residential",
            "floors": 1,
            "parameters": {"built_up_area": "120 m²", "finish_level": "standard"},
        }
        with patch.object(svc, "predict_quantity",
                          return_value={"quantity": 12.0, "method": "quantity_predictor",
                                        "is_item_level": False, "model_scope": "global",
                                        "prediction_confidence": 0.5,
                                        "feature_completeness": 0.7,
                                        "unknown_feature_count": 0,
                                        "unknown_feature_names": [],
                                        "allocation_mode": "direct"}), \
             patch.object(svc, "predict_category_total",
                          side_effect=RuntimeError("boom")):
            # Must not raise
            result = svc.compute_quantities(items, project_info, floorplan_geometry=None)

        assert result, "compute_quantities must return items even when Tier-2 fails"
        # Item should NOT be tagged as category_distributed when Tier-2 errors
        for it in result:
            assert it.get("quantity_source") != "category_distributed"
