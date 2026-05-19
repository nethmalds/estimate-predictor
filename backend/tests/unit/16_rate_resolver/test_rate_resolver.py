"""Unit tests for resolve_rate in rate_resolver.py.

Covers:
- BE-TC-088: Colombo location factor is 1.00 (no adjustment)
- BE-TC-089: Non-Colombo location reduces rate by defined factor
- BE-TC-090: Hard soil condition increases excavation rate
- BE-TC-091: Unknown location defaults to factor 1.00
- BE-TC-092: Zero base rate returns zero regardless of factors
"""
import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from services.pricing_process.rate_resolver import resolve_rate  # noqa: E402


def _project_info(location: str = "colombo", soil_condition: str = "ordinary soil") -> dict:
    return {"parameters": {"location": location, "soil_condition": soil_condition}}


def _item(rate: float, category: str = "brick_masonry") -> dict:
    return {"rate": rate, "category": category}


# ── BE-TC-088: Colombo → factor 1.00, rate unchanged ─────────────────────────

class TestColomboLocation:
    def test_colombo_rate_unchanged(self):
        item = _item(1000.0)
        adjusted = resolve_rate(item, _project_info("colombo"))
        assert adjusted == pytest.approx(1000.0)

    def test_colombo_no_rate_adjustment_key(self):
        item = _item(1000.0)
        resolve_rate(item, _project_info("colombo"))
        # Colombo has no adjustment, so rate_adjustment should not be injected
        assert "rate_adjustment" not in item

    def test_colombo_case_insensitive(self):
        item = _item(1000.0)
        adjusted = resolve_rate(item, _project_info("COLOMBO"))
        assert adjusted == pytest.approx(1000.0)


# ── BE-TC-089: Non-Colombo location reduces rate by defined factor ────────────

class TestNonColomboLocation:
    def test_badulla_applies_0_88_factor(self):
        item = _item(1000.0)
        adjusted = resolve_rate(item, _project_info("badulla"))
        assert adjusted == pytest.approx(880.0)

    def test_gampaha_applies_0_97_factor(self):
        item = _item(1000.0)
        adjusted = resolve_rate(item, _project_info("gampaha"))
        assert adjusted == pytest.approx(970.0)

    def test_nuwara_eliya_applies_0_87_factor(self):
        item = _item(1000.0)
        adjusted = resolve_rate(item, _project_info("nuwara eliya"))
        assert adjusted == pytest.approx(870.0)

    def test_rate_adjustment_key_injected_for_non_colombo(self):
        item = _item(1000.0)
        resolve_rate(item, _project_info("badulla"))
        assert "rate_adjustment" in item
        assert item["rate_adjustment"]["location_factor"] == pytest.approx(0.88)


# ── BE-TC-090: Hard soil condition increases excavation rate ──────────────────

class TestSoilConditionAdjustment:
    def test_hard_soil_excavation_factor_1_50(self):
        item = _item(1000.0, category="excavation_and_earthwork")
        adjusted = resolve_rate(item, _project_info("colombo", "hard soil"))
        assert adjusted == pytest.approx(1500.0)

    def test_hard_soil_piling_factor_1_25(self):
        item = _item(1000.0, category="piling_and_substructure")
        adjusted = resolve_rate(item, _project_info("colombo", "hard soil"))
        assert adjusted == pytest.approx(1250.0)

    def test_medium_soil_excavation_factor_1_20(self):
        item = _item(1000.0, category="excavation_and_earthwork")
        adjusted = resolve_rate(item, _project_info("colombo", "medium soil"))
        assert adjusted == pytest.approx(1200.0)

    def test_ordinary_soil_no_adjustment(self):
        item = _item(1000.0, category="excavation_and_earthwork")
        adjusted = resolve_rate(item, _project_info("colombo", "ordinary soil"))
        assert adjusted == pytest.approx(1000.0)

    def test_rock_excavation_factor_2_20(self):
        item = _item(1000.0, category="excavation_and_earthwork")
        adjusted = resolve_rate(item, _project_info("colombo", "rock"))
        assert adjusted == pytest.approx(2200.0)

    def test_soil_condition_only_applied_to_affected_categories(self):
        item = _item(1000.0, category="brick_masonry")
        adjusted = resolve_rate(item, _project_info("colombo", "hard soil"))
        # brick_masonry is not in soil adjustment table — rate unchanged
        assert adjusted == pytest.approx(1000.0)


# ── BE-TC-091: Unknown location defaults to factor 1.00 ──────────────────────

class TestUnknownLocation:
    def test_unknown_city_defaults_to_factor_1(self):
        item = _item(1000.0)
        adjusted = resolve_rate(item, _project_info("unknown_city"))
        assert adjusted == pytest.approx(1000.0)

    def test_empty_location_defaults_to_colombo_factor(self):
        item = _item(1000.0)
        adjusted = resolve_rate(item, {"parameters": {"location": ""}})
        assert adjusted == pytest.approx(1000.0)


# ── BE-TC-092: Zero base rate returns zero regardless of factors ──────────────

class TestZeroBaseRate:
    def test_zero_rate_returns_zero(self):
        item = _item(0.0)
        adjusted = resolve_rate(item, _project_info("badulla", "hard soil"))
        assert adjusted == 0.0

    def test_zero_rate_colombo_still_zero(self):
        item = _item(0.0, category="excavation_and_earthwork")
        adjusted = resolve_rate(item, _project_info("colombo", "rock"))
        assert adjusted == 0.0


# ── Combined location + soil factors ─────────────────────────────────────────

class TestCombinedFactors:
    def test_badulla_hard_soil_excavation_combined(self):
        # location=0.88, soil=1.50 → combined = 1000 * 0.88 * 1.50 = 1320
        item = _item(1000.0, category="excavation_and_earthwork")
        adjusted = resolve_rate(item, _project_info("badulla", "hard soil"))
        assert adjusted == pytest.approx(1320.0)
