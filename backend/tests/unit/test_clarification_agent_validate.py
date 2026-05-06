"""Unit tests for validate_wizard_payload in clarification_agent.py."""
import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from services.clarification_process.clarification_agent import validate_wizard_payload  # noqa: E402


# ── Helpers ────────────────────────────────────────────────────────────────────

def _base(overrides: dict | None = None) -> dict:
    base = {
        "building_type": "residential",
        "floor_count": 2,
        "floor_areas": [{"floor_label": "Ground Floor", "area_value": 200.0, "area_unit": "m2"}],
        "bedrooms": 3,
        "bathrooms": 2,
        "finish_level": "standard",
        "structural_system": "framed",
        "roof_type": "rc_flat_slab",
        "ceiling_type": "gypsum_mineral_fibre",
    }
    if overrides:
        base.update(overrides)
    return base


# ── Valid payload tests ────────────────────────────────────────────────────────

class TestValidPayloads:
    def test_valid_residential_payload(self):
        assert validate_wizard_payload(_base()) == {}

    def test_valid_commercial_payload(self):
        errors = validate_wizard_payload(_base({
            "building_type": "commercial",
            "primary_use_type": "Office",
            "washroom_count": 2,
        }))
        assert errors == {}

    def test_valid_industrial_payload(self):
        errors = validate_wizard_payload(_base({
            "building_type": "industrial",
            "facility_type": "Factory / Manufacturing",
            "heavy_machinery_load": "yes",
            "hazardous_materials": "no",
            "specialized_ventilation": "yes",
        }))
        assert errors == {}


# ── Required construction detail fields ───────────────────────────────────────

class TestRequiredConstructionDetails:
    def test_missing_finish_level(self):
        payload = _base()
        del payload["finish_level"]
        errors = validate_wizard_payload(payload)
        assert "finish_level" in errors

    def test_empty_finish_level(self):
        errors = validate_wizard_payload(_base({"finish_level": ""}))
        assert "finish_level" in errors

    def test_missing_structural_system(self):
        payload = _base()
        del payload["structural_system"]
        errors = validate_wizard_payload(payload)
        assert "structural_system" in errors

    def test_missing_roof_type(self):
        payload = _base()
        del payload["roof_type"]
        errors = validate_wizard_payload(payload)
        assert "roof_type" in errors

    def test_missing_ceiling_type(self):
        payload = _base()
        del payload["ceiling_type"]
        errors = validate_wizard_payload(payload)
        assert "ceiling_type" in errors


# ── Building type validation ───────────────────────────────────────────────────

class TestBuildingTypeValidation:
    def test_invalid_building_type(self):
        errors = validate_wizard_payload(_base({"building_type": "spaceship"}))
        assert "building_type" in errors

    def test_mixed_use_building_type_is_rejected(self):
        """mixed_use is not in the synced frontend contract and must be rejected."""
        errors = validate_wizard_payload(_base({"building_type": "mixed_use"}))
        assert "building_type" in errors


# ── Residential building specific ─────────────────────────────────────────────

class TestResidentialValidation:
    def test_residential_missing_bedrooms(self):
        payload = _base()
        del payload["bedrooms"]
        errors = validate_wizard_payload(payload)
        assert "bedrooms" in errors

    def test_residential_missing_bathrooms(self):
        payload = _base()
        del payload["bathrooms"]
        errors = validate_wizard_payload(payload)
        assert "bathrooms" in errors


# ── Commercial building specific ──────────────────────────────────────────────

class TestCommercialValidation:
    def test_commercial_missing_washroom_count(self):
        payload = _base({"building_type": "commercial"})
        payload.pop("washroom_count", None)
        errors = validate_wizard_payload(payload)
        assert "washroom_count" in errors

    def test_commercial_zero_washroom_count(self):
        errors = validate_wizard_payload(_base({
            "building_type": "commercial",
            "washroom_count": 0,
        }))
        assert "washroom_count" in errors

    def test_commercial_valid_washroom_count(self):
        errors = validate_wizard_payload(_base({
            "building_type": "commercial",
            "washroom_count": 1,
        }))
        assert "washroom_count" not in errors
