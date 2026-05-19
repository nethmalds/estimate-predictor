"""Integration test for the full estimation pipeline.

All external service calls (LLM, RAG, CV, Redis, DB) are patched with
controlled responses. Tests verify:
1. The complete data flow runs without raising exceptions
2. The output contains the required top-level keys
3. Confidence scores are in [0, 1]
4. No BOQ item has None description or unit after the pipeline
5. Pipeline respects a cancel event

Run with:
    pytest tests/integration/test_estimation_pipeline.py -v -m integration
"""
import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

pytestmark = pytest.mark.integration

# ── Fixture helpers ───────────────────────────────────────────────────────────

def _project_info() -> dict:
    """Realistic residential project_info after normalization and defaults."""
    return {
        "building_type": "residential",
        "floors": 2,
        "parameters": {
            "bedrooms": 3,
            "bathrooms": 2,
            "built_up_area": 250.0,
            "finish_level": "standard",
            "structural_system": "framed",
            "roof_type": "clay_tile",
            "ceiling_type": "plastered",
            "soil_condition": "normal",
        },
        "explicit_parameters": ["bedrooms", "bathrooms", "finish_level"],
        "value_sources": {},
        "applied_defaults": [],
    }


def _mock_boq_items(count: int = 5) -> list[dict]:
    return [
        {
            "description": f"BOQ item {i}",
            "category": "brick_masonry" if i % 2 == 0 else "concrete",
            "section": "Masonry" if i % 2 == 0 else "Concrete",
            "unit": "m2",
            "source": "llm_baseline",
        }
        for i in range(count)
    ]


def _mock_matched_items(items: list[dict]) -> list[dict]:
    return [
        {
            **item,
            "bsr_item_no": f"A{i + 1}.1",
            "bsr_description": item["description"],
            "rate": 2000.0 + i * 100,
            "match_confidence": 0.85,
            "match_type": "confirmed",
            "needs_rate_review": False,
        }
        for i, item in enumerate(items)
    ]


def _mock_quantified_items(items: list[dict]) -> list[dict]:
    return [{**item, "quantity": 10.0 + i} for i, item in enumerate(items)]


def _mock_costed_items(items: list[dict]) -> dict:
    priced = [{**item, "cost": item.get("quantity", 10.0) * item.get("rate", 2000.0)} for item in items]
    base_total = sum(it["cost"] for it in priced)
    return {
        "items": priced,
        "base_total": base_total,
        "external_works_total": 0.0,
        "preliminaries": base_total * 0.08,
        "contingencies": base_total * 0.05,
        "total": base_total * 1.13,
        "subtotals": {"masonry": base_total * 0.6, "concrete": base_total * 0.4},
    }


# ── BE-TC-046 & 047 & 048: Output keys, confidence range, non-empty BOQ ───────

class TestEstimationPipelineOutput:
    """Verify the pipeline output structure when all stages succeed."""

    def _run_with_mocks(self, project_info=None, cancel_event=None):
        if project_info is None:
            project_info = _project_info()

        raw_boq = _mock_boq_items()
        matched = _mock_matched_items(raw_boq)
        quantified = _mock_quantified_items(matched)
        costed = _mock_costed_items(quantified)

        mock_confidence = {
            "score": 0.83,
            "breakdown": {"quantity_coverage": 0.1, "match_rate": 0.05},
            "section_breakdown": {"Masonry": {"item_count": 3, "matched": 3, "unmatched": 0, "contractual": 0}},
        }

        with (
            patch("application.pipelines.estimation_pipeline.apply_defaults", return_value=project_info),
            patch("application.pipelines.estimation_pipeline.build_final_boq_items", return_value=raw_boq),
            patch("application.pipelines.estimation_pipeline.validate_generated_boq_items",
                  return_value={"is_valid": True, "errors": [], "warnings": []}),
            patch.object(
                __import__("application.pipelines.estimation_pipeline", fromlist=["rag_service"]).rag_service,
                "match_boq_items_batch",
                return_value=matched,
            ),
            patch("application.pipelines.estimation_pipeline.compute_quantities", return_value=quantified),
            patch("application.pipelines.estimation_pipeline.validate_quantities",
                  return_value={"valid_items": len(quantified), "anomalies": []}),
            patch("application.pipelines.estimation_pipeline.calculate_costs", return_value=costed),
            patch("application.pipelines.estimation_pipeline.score_confidence", return_value=mock_confidence),
            patch("application.pipelines.estimation_pipeline.build_report",
                  return_value={"summary": "Test report"}),
            patch("application.pipelines.estimation_pipeline._build_source_summary",
                  return_value={"boq_method": "llm", "quantity_method": "rule_based"}),
        ):
            from application.pipelines.estimation_pipeline import (
                run_estimation_pipeline_from_project_info,
            )
            return run_estimation_pipeline_from_project_info(
                project_info=project_info,
                floorplan_urls=[],
                cancel_event=cancel_event,
            )

    def test_output_has_required_top_level_keys(self):
        result = self._run_with_mocks()
        required_keys = {"boq_items", "costs", "confidence", "report", "floorplan"}
        assert required_keys.issubset(result.keys()), (
            f"Missing keys: {required_keys - result.keys()}"
        )

    def test_confidence_score_is_in_valid_range(self):
        result = self._run_with_mocks()
        score = result["confidence"]["score"]
        assert 0.0 <= score <= 1.0, f"confidence.score out of range: {score}"

    def test_boq_items_are_non_empty(self):
        result = self._run_with_mocks()
        assert len(result["boq_items"]) > 0

    def test_no_boq_item_has_none_description(self):
        result = self._run_with_mocks()
        for item in result["boq_items"]:
            desc = item.get("description") or item.get("bsr_description")
            assert desc is not None, f"Item has no description: {item}"

    def test_no_boq_item_has_none_unit(self):
        result = self._run_with_mocks()
        for item in result["boq_items"]:
            assert item.get("unit") is not None, f"Item has no unit: {item}"

    # BE-TC-049: costs.total is present and positive
    def test_costs_has_total(self):
        result = self._run_with_mocks()
        assert "total" in result["costs"]
        assert result["costs"]["total"] > 0

    # BE-TC-050: floorplan.available is false when no URLs supplied
    def test_floorplan_meta_shows_unavailable_when_no_urls(self):
        result = self._run_with_mocks()
        assert result["floorplan"]["available"] is False


# ── Floor-scope allocation integration check ─────────────────────────────────

class TestComputeQuantitiesFloorAllocation:
    """Exercise compute_quantities end-to-end with floor-variant BOQ items.

    Reproduces the bug shape from the screenshot: 4 brick masonry items
    (external/internal × ground/first floor) that the calculator would
    otherwise stamp with an identical whole-building quantity.  Verifies
    the floor-scope allocation pass redistributes the total.
    """

    def _floor_variant_items(self) -> list[dict]:
        # All 4 items in the same category & near-identical signature —
        # the calculator will assign each the same whole-building qty.
        base = {
            "category": "brick_masonry",
            "section": "Brick Masonry",
            "unit": "m²",
            "preferred_unit": "m²",
            "unit_kind": "continuous",
            "source": "llm_baseline",
            "floors": 2,
            "work_category": "Brick Masonry",
            "material_type": "Masonry",
        }
        return [
            {**base, "description": 'Brick masonry 1:5 9" external walls ground floor', "floor_scope": "ground"},
            {**base, "description": 'Brick masonry 1:5 4.5" internal partition walls ground floor', "floor_scope": "ground"},
            {**base, "description": 'Brick masonry 1:5 9" external walls first floor',  "floor_scope": "first"},
            {**base, "description": 'Brick masonry 1:5 4.5" internal partition walls first floor', "floor_scope": "first"},
        ]

    def _project_info_2_floors(self) -> dict:
        return {
            "building_type": "residential",
            "floors": 2,
            "parameters": {
                "bedrooms": 3,
                "bathrooms": 2,
                "built_up_area": "235 m2",
                "finish_level": "standard",
                "structural_system": "framed",
            },
            "per_floor_area_m2": {"ground": 117.5, "first": 117.5},
            "explicit_parameters": ["bedrooms", "bathrooms"],
            "value_sources": {},
            "applied_defaults": [],
        }

    def test_per_floor_items_no_longer_share_quantity(self):
        from services.quantity_gen_process.service import compute_quantities

        result = compute_quantities(
            self._floor_variant_items(),
            self._project_info_2_floors(),
            floorplan_geometry=None,
        )
        quantities = [r["quantity"] for r in result]
        # Bug fixed: no two sibling items in this group share an identical qty.
        assert len(set(quantities)) >= 2, (
            f"All 4 floor variants still share identical quantity {quantities[0]} — "
            "allocator did not run."
        )

    def test_group_sum_matches_whole_building_total(self):
        from services.quantity_gen_process.rule_based_calculator import calculate_parametric
        from services.quantity_gen_process.service import compute_quantities

        items = self._floor_variant_items()
        info = self._project_info_2_floors()

        # Expected whole-building total = single-pass parametric calc for the category.
        whole_qty, _ = calculate_parametric(items[0], info)
        assert whole_qty is not None and whole_qty > 0, "Sanity: parametric calc must produce a value"

        result = compute_quantities(items, info, floorplan_geometry=None)
        group_sum = sum(r["quantity"] for r in result)
        # Within 2% of the single whole-building number.
        assert abs(group_sum - whole_qty) / whole_qty < 0.02, (
            f"Group sum {group_sum} should be ≈ whole-building {whole_qty} (within 2%)."
        )

    def test_allocation_method_recorded(self):
        from services.quantity_gen_process.service import compute_quantities

        result = compute_quantities(
            self._floor_variant_items(),
            self._project_info_2_floors(),
            floorplan_geometry=None,
        )
        methods = {r.get("quantity_allocation_method") for r in result}
        # All 4 items in the group must be tagged with the same allocation method.
        assert methods == {"per_floor_area_x_qs_weight"}, f"Unexpected methods: {methods}"


# ── BE-TC-051: Cancel event raises PipelineCancelledError ────────────────────

class TestEstimationPipelineCancellation:
    """Verify that the pipeline respects a cancel event."""

    def test_raises_when_cancel_event_set_before_run(self):
        from application.pipelines.estimation_pipeline import PipelineCancelledError

        cancel_event = threading.Event()
        cancel_event.set()

        with (
            patch("application.pipelines.estimation_pipeline.apply_defaults",
                  return_value=_project_info()),
            patch("application.pipelines.estimation_pipeline.build_final_boq_items",
                  return_value=_mock_boq_items()),
            patch("application.pipelines.estimation_pipeline.validate_generated_boq_items",
                  return_value={"is_valid": True, "errors": [], "warnings": []}),
        ):
            from application.pipelines.estimation_pipeline import (
                run_estimation_pipeline_from_project_info,
            )
            with pytest.raises(PipelineCancelledError):
                run_estimation_pipeline_from_project_info(
                    project_info=_project_info(),
                    floorplan_urls=[],
                    cancel_event=cancel_event,
                )


# ── BE-TC-052: Progress callback receives stage events ───────────────────────

class TestEstimationPipelineProgressCallback:
    """Verify that the pipeline emits progress events."""

    def test_progress_callback_receives_stage_events(self):
        emitted: list[tuple] = []

        def capture_progress(stage: str, status: str, data):
            emitted.append((stage, status))

        raw_boq = _mock_boq_items()
        matched = _mock_matched_items(raw_boq)
        quantified = _mock_quantified_items(matched)
        costed = _mock_costed_items(quantified)
        project_info = _project_info()

        mock_confidence = {"score": 0.8, "breakdown": {}, "section_breakdown": {}}

        with (
            patch("application.pipelines.estimation_pipeline.apply_defaults", return_value=project_info),
            patch("application.pipelines.estimation_pipeline.build_final_boq_items", return_value=raw_boq),
            patch("application.pipelines.estimation_pipeline.validate_generated_boq_items",
                  return_value={"is_valid": True, "errors": [], "warnings": []}),
            patch.object(
                __import__("application.pipelines.estimation_pipeline", fromlist=["rag_service"]).rag_service,
                "match_boq_items_batch",
                return_value=matched,
            ),
            patch("application.pipelines.estimation_pipeline.compute_quantities", return_value=quantified),
            patch("application.pipelines.estimation_pipeline.validate_quantities",
                  return_value={"valid_items": len(quantified), "anomalies": []}),
            patch("application.pipelines.estimation_pipeline.calculate_costs", return_value=costed),
            patch("application.pipelines.estimation_pipeline.score_confidence", return_value=mock_confidence),
            patch("application.pipelines.estimation_pipeline.build_report", return_value={"summary": ""}),
            patch("application.pipelines.estimation_pipeline._build_source_summary", return_value={}),
        ):
            from application.pipelines.estimation_pipeline import (
                run_estimation_pipeline_from_project_info,
            )
            run_estimation_pipeline_from_project_info(
                project_info=project_info,
                floorplan_urls=[],
                progress_callback=capture_progress,
            )

        stage_names = [s for s, _ in emitted]
        assert "baseline_boq" in stage_names
        assert "bsr_matching" in stage_names
        assert "cost_calculation" in stage_names
