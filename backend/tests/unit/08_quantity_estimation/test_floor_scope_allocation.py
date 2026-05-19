"""Unit tests for floor-scope quantity allocation.

Verifies that the post-processing allocator redistributes a duplicated
whole-building quantity across per-floor / per-variant sibling items so
that the group sums to the correct total.
"""
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from services.quantity_gen_process.service import (  # noqa: E402
    _allocate_floor_scoped_quantities,
)


def _make_item(
    description: str,
    quantity: float,
    category: str = "brick_masonry",
    floor_scope: str = "all",
    unit: str = "m²",
    unit_kind: str = "continuous",
) -> dict:
    return {
        "description": description,
        "category": category,
        "quantity": quantity,
        "final_quantity": quantity,
        "unit": unit,
        "preferred_unit": unit,
        "unit_kind": unit_kind,
        "floor_scope": floor_scope,
        "quantity_source": "rule_based",
        "quantity_candidates": [],
        "reconciliation_summary": {},
    }


# ── BE-TC-FA-01: Bug-signature case (per-floor × per-orientation siblings) ────

class TestPerFloorAndOrientationSplit:
    """The exact bug shape from the screenshot: 2 floors × 2 wall types."""

    def _group(self) -> list[dict]:
        # Realistic BSR-style descriptions: external walls are typically 9" (full
        # brick) and internal partitions are 4.5" — QS weights distinguish them.
        return [
            _make_item('Brick masonry 1:5 9" external walls ground floor', 305.73, floor_scope="ground"),
            _make_item('Brick masonry 1:5 4.5" internal partition walls ground floor', 305.73, floor_scope="ground"),
            _make_item('Brick masonry 1:5 9" external walls first floor', 305.73, floor_scope="first"),
            _make_item('Brick masonry 1:5 4.5" internal partition walls first floor', 305.73, floor_scope="first"),
        ]

    def test_sum_preserves_whole_building_total(self):
        items = self._group()
        project_info = {
            "floors": 2,
            "per_floor_area_m2": {"ground": 117.5, "first": 117.5},
        }
        result = _allocate_floor_scoped_quantities(items, project_info)
        total = sum(it["quantity"] for it in result)
        assert abs(total - 305.73) < 0.05, f"Group sum {total} should preserve original {305.73}"

    def test_quantities_now_differ(self):
        items = self._group()
        project_info = {
            "floors": 2,
            "per_floor_area_m2": {"ground": 117.5, "first": 117.5},
        }
        result = _allocate_floor_scoped_quantities(items, project_info)
        quantities = [it["quantity"] for it in result]
        # 9" walls get QS weight 70, 4.5" get 30 → external vs internal differ.
        assert len(set(quantities)) >= 2

    def test_method_tagged(self):
        items = self._group()
        result = _allocate_floor_scoped_quantities(items, {"floors": 2, "per_floor_area_m2": {"ground": 117.5, "first": 117.5}})
        for it in result:
            assert it.get("quantity_allocation_method") == "per_floor_area_x_qs_weight"


# ── BE-TC-FA-02: Single floor (no allocation should run) ──────────────────────

class TestSingleFloorNoAllocation:
    def test_size_one_group_untouched(self):
        items = [_make_item("Brick masonry 1:5", 100.0, floor_scope="all")]
        result = _allocate_floor_scoped_quantities(items, {"floors": 1})
        assert result[0]["quantity"] == 100.0
        assert "quantity_allocation_method" not in result[0]


# ── BE-TC-FA-03: Group sum already ≈ whole-building (gate triggers) ───────────

class TestGateSkipsCorrectlySplitGroups:
    def test_no_allocation_when_group_sum_matches_whole_building(self):
        # Group items legitimately summing to ≈ whole-building total.
        # whole_qty for brick_masonry with built_up_area=235 m², 2 floors ≈ 568 m².
        # Per-floor split (each ≈ 284) sums to 568 — already correct.
        items = [
            _make_item("Brick masonry 1:5 ground floor", 284.0, floor_scope="ground"),
            _make_item("Brick masonry 1:5 first floor", 284.0, floor_scope="first"),
        ]
        project_info = {
            "floors": 2,
            "parameters": {
                "built_up_area": "235 m2",
                "bedrooms": 3,
                "bathrooms": 2,
            },
            "per_floor_area_m2": {"ground": 117.5, "first": 117.5},
        }
        result = _allocate_floor_scoped_quantities(items, project_info)
        # Group sum already matches whole-building → allocator skips.
        assert result[0]["quantity"] == 284.0
        assert result[1]["quantity"] == 284.0
        assert "quantity_allocation_method" not in result[0]


# ── BE-TC-FA-04: Lump-sum and discrete categories are skipped ─────────────────

class TestSkipLumpSumAndDiscrete:
    def test_preliminary_category_skipped(self):
        items = [
            _make_item("Preliminaries ground floor", 1.0, category="preliminary_and_general", floor_scope="ground"),
            _make_item("Preliminaries first floor", 1.0, category="preliminary_and_general", floor_scope="first"),
        ]
        result = _allocate_floor_scoped_quantities(items, {"floors": 2})
        for it in result:
            assert it["quantity"] == 1.0
            assert "quantity_allocation_method" not in it

    def test_roofing_category_skipped(self):
        items = [
            _make_item("Clay tile roofing ground floor", 200.0, category="roofing_and_ceiling", floor_scope="ground"),
            _make_item("Clay tile roofing first floor", 200.0, category="roofing_and_ceiling", floor_scope="first"),
        ]
        result = _allocate_floor_scoped_quantities(items, {"floors": 2})
        for it in result:
            assert it["quantity"] == 200.0
            assert "quantity_allocation_method" not in it

    def test_discrete_unit_kind_skipped(self):
        items = [
            _make_item("Door ground floor", 4.0, category="doors_windows_and_glazing",
                       floor_scope="ground", unit="Nr", unit_kind="discrete"),
            _make_item("Door first floor", 4.0, category="doors_windows_and_glazing",
                       floor_scope="first", unit="Nr", unit_kind="discrete"),
        ]
        result = _allocate_floor_scoped_quantities(items, {"floors": 2})
        for it in result:
            assert it["quantity"] == 4.0


# ── BE-TC-FA-05: Falls back to QS weight, then equal split ────────────────────

class TestFallbackWeights:
    def test_no_per_floor_area_uses_qs_weight(self):
        items = [
            _make_item('Brick masonry 9" external walls ground floor', 100.0, floor_scope="ground"),
            _make_item('Brick masonry 4.5" internal partition walls ground floor', 100.0, floor_scope="ground"),
        ]
        # Same floor → no per-floor split possible; QS weights vary on description.
        result = _allocate_floor_scoped_quantities(items, {"floors": 1})
        methods = {it.get("quantity_allocation_method") for it in result}
        assert "qs_weight" in methods or "per_floor_area_x_qs_weight" in methods
        assert abs(sum(it["quantity"] for it in result) - 100.0) < 0.05

    def test_equal_split_when_no_signals(self):
        # Floor-variant siblings, no per_floor_area_m2 data, no QS-distinguishable
        # tokens → fall back to equal split.
        items = [
            _make_item("Brick masonry generic ground floor", 60.0, floor_scope="ground"),
            _make_item("Brick masonry generic first floor", 60.0, floor_scope="first"),
        ]
        result = _allocate_floor_scoped_quantities(items, {"floors": 2})
        assert result[0]["quantity_allocation_method"] == "equal_split"
        assert abs(sum(it["quantity"] for it in result) - 60.0) < 0.05
        assert abs(result[0]["quantity"] - 30.0) < 0.05


# ── BE-TC-FA-06: Floor-count mismatch triggers review flag ────────────────────

class TestMismatchTriggersReview:
    def test_three_floor_variants_for_two_floor_project(self):
        items = [
            _make_item("Brick masonry ground floor", 100.0, floor_scope="ground"),
            _make_item("Brick masonry first floor", 100.0, floor_scope="first"),
            _make_item("Brick masonry second floor", 100.0, floor_scope="second"),
        ]
        result = _allocate_floor_scoped_quantities(items, {"floors": 2})
        for it in result:
            assert it.get("needs_rate_review") is True
            assert "does not match project floor_count" in (it.get("quantity_warning") or "")


# ── BE-TC-FA-07: Allocation transparency on each item ─────────────────────────

class TestTransparency:
    def test_allocation_candidate_appended(self):
        items = [
            _make_item("Brick masonry ground floor", 200.0, floor_scope="ground"),
            _make_item("Brick masonry first floor", 200.0, floor_scope="first"),
        ]
        result = _allocate_floor_scoped_quantities(items, {"floors": 2, "per_floor_area_m2": {"ground": 100.0, "first": 100.0}})
        for it in result:
            cands = it["quantity_candidates"]
            assert any(c["candidate_type"] == "allocation" for c in cands)

    def test_reconciliation_note_set(self):
        items = [
            _make_item("Brick masonry ground floor", 200.0, floor_scope="ground"),
            _make_item("Brick masonry first floor", 200.0, floor_scope="first"),
        ]
        result = _allocate_floor_scoped_quantities(items, {"floors": 2, "per_floor_area_m2": {"ground": 100.0, "first": 100.0}})
        for it in result:
            assert "allocation_note" in it["reconciliation_summary"]


# ── BE-TC-FA-09: Asymmetric per-floor areas with near-equal item quantities ───

class TestAsymmetricFloorAreasTriggerAllocation:
    """Bug shape from the second screenshot: 2 items with near-identical
    quantities because the calculator stamped both with the same whole-building
    value, but the user provided asymmetric per-floor areas (1800 vs 1300
    sqft).  Allocator must redistribute by per-floor area ratio even when the
    group sum is close to the whole-building reference.
    """

    def test_redistribution_by_per_floor_area_ratio(self):
        items = [
            _make_item(
                "Construct 150 mm thick brick masonry external walls on ground floor",
                333.38, floor_scope="ground",
            ),
            _make_item(
                "Construct 150 mm thick brick masonry external walls on first floor",
                333.38, floor_scope="first",
            ),
        ]
        project_info = {
            "floors": 2,
            "parameters": {"built_up_area": "3100 sqft", "bedrooms": 3, "bathrooms": 2},
            "per_floor_area_m2": {"ground": 167.22, "first": 120.77},
        }
        result = _allocate_floor_scoped_quantities(items, project_info)
        # Allocator should run because per-floor data is asymmetric and items are equal.
        assert result[0]["quantity_allocation_method"] == "per_floor_area"
        # Sum is preserved (was already correct).
        assert abs(sum(r["quantity"] for r in result) - 666.76) < 0.1
        # Quantities now reflect 58 / 42 split.
        assert result[0]["quantity"] > result[1]["quantity"]
        ratio = result[0]["quantity"] / result[1]["quantity"]
        expected = 167.22 / 120.77
        assert abs(ratio - expected) < 0.01

    def test_symmetric_floor_areas_skip_when_within_threshold(self):
        # Both floors equal area + items already equal at near whole-building scale
        # → nothing to fix.
        items = [
            _make_item("Brick masonry external walls ground floor", 284.0, floor_scope="ground"),
            _make_item("Brick masonry external walls first floor",  284.0, floor_scope="first"),
        ]
        project_info = {
            "floors": 2,
            "parameters": {"built_up_area": "235 m2", "bedrooms": 3, "bathrooms": 2},
            "per_floor_area_m2": {"ground": 117.5, "first": 117.5},
        }
        result = _allocate_floor_scoped_quantities(items, project_info)
        # Floor areas are symmetric AND items already at whole-building scale → skip.
        assert "quantity_allocation_method" not in result[0]
        assert result[0]["quantity"] == 284.0


# ── BE-TC-FA-10: Group already at correct whole-building scale → no re-split ──

class TestNoDoubleSplit:
    def test_skips_when_group_sum_already_matches_whole_building(self):
        # Group sum (568) already ≈ parametric whole-building for 2-floor 235 m²
        # → over-count gate skips, items are left alone even when previously
        # split through the ML distribution path.
        items = [
            {
                "description": "Brick masonry 1:5 ground floor",
                "category": "brick_masonry",
                "quantity": 284.0,
                "final_quantity": 284.0,
                "unit": "m²", "preferred_unit": "m²", "unit_kind": "continuous",
                "floor_scope": "ground",
                "quantity_source": "quantity_predictor",
                "quantity_candidates": [{
                    "candidate_type": "quantity_predictor",
                    "source_payload": {"allocation_mode": "global_allocation"},
                }],
                "reconciliation_summary": {"source": "quantity_predictor", "method": "weighted_fusion"},
            },
            {
                "description": "Brick masonry 1:5 first floor",
                "category": "brick_masonry",
                "quantity": 284.0,
                "final_quantity": 284.0,
                "unit": "m²", "preferred_unit": "m²", "unit_kind": "continuous",
                "floor_scope": "first",
                "quantity_source": "quantity_predictor",
                "quantity_candidates": [{
                    "candidate_type": "quantity_predictor",
                    "source_payload": {"allocation_mode": "global_allocation"},
                }],
                "reconciliation_summary": {"source": "quantity_predictor", "method": "weighted_fusion"},
            },
        ]
        project_info = {
            "floors": 2,
            "parameters": {
                "built_up_area": "235 m2",
                "bedrooms": 3,
                "bathrooms": 2,
            },
        }
        result = _allocate_floor_scoped_quantities(items, project_info)
        for it in result:
            assert it["quantity"] == 284.0
            assert "quantity_allocation_method" not in it
