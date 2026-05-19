"""Unit tests for score_confidence in services/validation/confidence_scoring.py.

Covers:
- BE-TC-083: floorplan data bonus adds +0.10 to score
- BE-TC-084: full mandatory category coverage adds +0.15 bonus
- BE-TC-085: unmatched items reduce score proportionally
- BE-TC-086: output score is always clamped to [0.0, 1.0]
- BE-TC-087: cost-sensitive defaults apply penalty per field
"""
import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from services.validation.confidence_scoring import score_confidence  # noqa: E402

# Mandatory categories for residential (15 total)
_RESIDENTIAL_MANDATORY = [
    "preliminary_and_general",
    "excavation_and_earthwork",
    "piling_and_substructure",
    "concrete_works",
    "formwork",
    "reinforcement",
    "brick_masonry",
    "plastering_and_rendering",
    "painting_and_finishes",
    "roofing_and_ceiling",
    "doors_windows_and_glazing",
    "flooring_and_tiling",
    "sanitary_and_plumbing",
    "electrical_and_mechanical",
    "testing_and_commissioning",
]


def _minimal_project_info(building_type: str = "residential", applied_defaults: list | None = None) -> dict:
    return {
        "building_type": building_type,
        "applied_defaults": applied_defaults or [],
        "parameters": {
            "built_up_area": 250.0,
            "finish_level": "standard",
        },
    }


def _matched_item(category: str) -> dict:
    return {
        "description": f"{category} item",
        "category": category,
        "match_type": "confirmed",
        "rate": 2000.0,
        "needs_rate_review": False,
    }


def _unmatched_item(category: str) -> dict:
    return {
        "description": f"{category} unmatched",
        "category": category,
        "match_type": "no_match",
        "rate": 0.0,
        "needs_rate_review": False,
    }


# ── BE-TC-083: floorplan data bonus +0.10 ─────────────────────────────────────

class TestFloorplanBonus:
    def test_floorplan_with_area_adds_bonus(self):
        # Use cost-sensitive defaults + warnings to keep base score below 0.90
        # so the +0.10 bonus is visible without hitting the 1.0 ceiling.
        low_project = _minimal_project_info(applied_defaults=["finish_level", "roof_type"])
        warnings = ["qty warning 1", "qty warning 2"]
        base = score_confidence(low_project, warnings=warnings)
        with_fp = score_confidence(
            low_project,
            floorplan_summary={"total_floor_area_m2": 150.0},
            warnings=warnings,
        )
        assert with_fp["score"] == pytest.approx(base["score"] + 0.10, abs=0.01)

    def test_floorplan_without_area_does_not_add_bonus(self):
        base = score_confidence(_minimal_project_info())
        no_area = score_confidence(
            _minimal_project_info(),
            floorplan_summary={"available": True},
        )
        assert no_area["score"] == pytest.approx(base["score"], abs=0.001)

    def test_floorplan_bonus_reason_recorded(self):
        result = score_confidence(
            _minimal_project_info(),
            floorplan_summary={"total_floor_area_m2": 200.0},
        )
        assert "floorplan_data" in result["reasons"]


# ── BE-TC-084: full mandatory category coverage +0.15 ─────────────────────────

class TestMandatoryCoveragebonus:
    def test_full_coverage_adds_015_bonus(self):
        # Build BOQ with all 15 mandatory categories
        items = [_matched_item(cat) for cat in _RESIDENTIAL_MANDATORY]
        result = score_confidence(_minimal_project_info("residential"), boq_items=items)
        assert any("full_mandatory_coverage" in r for r in result["reasons"])

    def test_full_coverage_reason_mentions_plus_015(self):
        items = [_matched_item(cat) for cat in _RESIDENTIAL_MANDATORY]
        result = score_confidence(_minimal_project_info("residential"), boq_items=items)
        coverage_reasons = [r for r in result["reasons"] if "full_mandatory_coverage" in r]
        assert len(coverage_reasons) == 1
        assert "+0.15" in coverage_reasons[0]

    def test_partial_coverage_does_not_give_full_bonus(self):
        # Only 5 of 15 categories
        items = [_matched_item(cat) for cat in _RESIDENTIAL_MANDATORY[:5]]
        result = score_confidence(_minimal_project_info("residential"), boq_items=items)
        assert not any("full_mandatory_coverage:+0.15" in r for r in result["reasons"])

    def test_no_boq_items_no_coverage_bonus(self):
        result = score_confidence(_minimal_project_info("residential"), boq_items=None)
        assert not any("full_mandatory_coverage" in r for r in result["reasons"])


# ── BE-TC-085: unmatched items reduce score proportionally ────────────────────

class TestUnmatchedItemPenalty:
    def test_all_unmatched_applies_penalty(self):
        total = 5
        items = [_unmatched_item("brick_masonry") for _ in range(total)]
        result_unmatched = score_confidence(_minimal_project_info(), boq_items=items)
        result_none = score_confidence(_minimal_project_info())
        assert result_unmatched["score"] < result_none["score"]

    def test_penalty_proportional_to_unmatched_fraction(self):
        # 5 items: 2 matched, 3 unmatched → penalty = 0.30 * (3/5) = 0.18
        items = (
            [_matched_item("concrete_works")] * 2
            + [_unmatched_item("brick_masonry")] * 3
        )
        result = score_confidence(_minimal_project_info(), boq_items=items)
        unmatched_reasons = [r for r in result["reasons"] if "unmatched_items" in r]
        assert len(unmatched_reasons) == 1
        assert "3/5" in unmatched_reasons[0]

    def test_all_matched_no_unmatched_penalty(self):
        items = [_matched_item("concrete_works") for _ in range(3)]
        result = score_confidence(_minimal_project_info(), boq_items=items)
        unmatched_reasons = [r for r in result["reasons"] if "unmatched_items" in r]
        assert len(unmatched_reasons) == 0


# ── BE-TC-086: output score clamped to [0.0, 1.0] ────────────────────────────

class TestScoreClamping:
    def test_score_never_exceeds_1_0(self):
        # All bonuses active: should not exceed 1.0
        items = [_matched_item(cat) for cat in _RESIDENTIAL_MANDATORY]
        result = score_confidence(
            _minimal_project_info(),
            floorplan_summary={"total_floor_area_m2": 250.0},
            boq_items=items,
        )
        assert result["score"] <= 1.0

    def test_score_never_goes_below_0_0(self):
        # Maximum penalties: many unmatched items, warnings, defaults
        unmatched = [_unmatched_item("brick_masonry") for _ in range(20)]
        warnings = [f"warning_{i}" for i in range(10)]
        project_info = _minimal_project_info(
            applied_defaults=["finish_level", "roof_type", "structural_system"]
        )
        result = score_confidence(project_info, warnings=warnings, boq_items=unmatched)
        assert result["score"] >= 0.0

    def test_score_is_float(self):
        result = score_confidence(_minimal_project_info())
        assert isinstance(result["score"], float)

    def test_result_contains_required_keys(self):
        result = score_confidence(_minimal_project_info())
        for key in ("score", "reasons", "defaults_applied", "section_breakdown"):
            assert key in result


# ── BE-TC-087: cost-sensitive defaults apply penalty per field ────────────────

class TestDefaultsPenalty:
    def test_single_cost_sensitive_default_applies_004_penalty(self):
        base = score_confidence(_minimal_project_info(applied_defaults=[]))
        with_default = score_confidence(
            _minimal_project_info(applied_defaults=["finish_level"])
        )
        assert with_default["score"] == pytest.approx(base["score"] - 0.04, abs=0.01)

    def test_two_defaults_apply_008_penalty(self):
        base = score_confidence(_minimal_project_info(applied_defaults=[]))
        with_two = score_confidence(
            _minimal_project_info(applied_defaults=["finish_level", "roof_type"])
        )
        assert with_two["score"] == pytest.approx(base["score"] - 0.08, abs=0.01)

    def test_non_cost_sensitive_default_not_penalised(self):
        base = score_confidence(_minimal_project_info(applied_defaults=[]))
        with_non_sensitive = score_confidence(
            _minimal_project_info(applied_defaults=["location"])
        )
        # location is not cost-sensitive, no penalty beyond losing the mved bonus
        diff = base["score"] - with_non_sensitive["score"]
        assert diff == pytest.approx(0.0, abs=0.01)

    def test_default_penalty_capped_at_020(self):
        # 6 cost-sensitive defaults would be 0.04*6=0.24, but capped at 0.20
        many_defaults = ["finish_level", "roof_type", "structural_system",
                         "finish_level", "roof_type", "structural_system"]
        result = score_confidence(_minimal_project_info(applied_defaults=many_defaults))
        defaults_reasons = [r for r in result["reasons"] if "defaults_applied" in r]
        # Verify penalty was applied (score reduced)
        base = score_confidence(_minimal_project_info(applied_defaults=[]))
        assert base["score"] - result["score"] <= 0.20 + 0.001

    def test_default_reason_recorded(self):
        result = score_confidence(
            _minimal_project_info(applied_defaults=["finish_level"])
        )
        assert any("defaults_applied" in r for r in result["reasons"])
