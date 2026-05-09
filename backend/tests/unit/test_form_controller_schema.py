"""Unit tests for WizardFormPayload Pydantic schema in form_controller.py."""
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

# Ensure backend root is importable
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.api.controllers.form_controller import WizardFormPayload  # noqa: E402


# ── Helpers ────────────────────────────────────────────────────────────────────

def _minimal(overrides: dict | None = None) -> dict:
    """Return a minimal valid residential payload."""
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


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestResidentialPayload:
    def test_minimal_residential_payload_valid(self):
        payload = WizardFormPayload(**_minimal())
        assert payload.building_type == "residential"
        assert payload.bedrooms == 3
        assert payload.bathrooms == 2

    def test_floor_count_bounds(self):
        with pytest.raises(ValidationError):
            WizardFormPayload(**_minimal({"floor_count": 0}))
        with pytest.raises(ValidationError):
            WizardFormPayload(**_minimal({"floor_count": 101}))

    def test_bedroom_bounds(self):
        with pytest.raises(ValidationError):
            WizardFormPayload(**_minimal({"bedrooms": 0}))


class TestCommercialPayload:
    def test_minimal_commercial_payload_valid(self):
        payload = WizardFormPayload(**_minimal({
            "building_type": "commercial",
            "primary_use_type": "Office",
            "washroom_count": 4,
        }))
        assert payload.primary_use_type == "Office"
        assert payload.washroom_count == 4

    def test_washroom_count_must_be_positive(self):
        with pytest.raises(ValidationError):
            WizardFormPayload(**_minimal({
                "building_type": "commercial",
                "washroom_count": 0,
            }))

    def test_washroom_count_optional_for_residential(self):
        """Residential payloads don't need washroom_count."""
        payload = WizardFormPayload(**_minimal())
        assert payload.washroom_count is None


class TestIndustrialPayload:
    def test_minimal_industrial_payload_valid(self):
        payload = WizardFormPayload(**_minimal({
            "building_type": "industrial",
            "facility_type": "Factory / Manufacturing",
            "heavy_machinery_load": "yes",
            "hazardous_materials": "no",
            "specialized_ventilation": "yes",
        }))
        assert payload.facility_type == "Factory / Manufacturing"
        assert payload.heavy_machinery_load == "yes"
        assert payload.specialized_ventilation == "yes"


class TestFloorplanUrls:
    def test_floorplan_urls_accepted_as_list(self):
        payload = WizardFormPayload(**_minimal({"floorplan_urls": ["https://example.com/a.jpg", "https://example.com/b.jpg"]}))
        assert len(payload.floorplan_urls) == 2

    def test_floorplan_urls_defaults_to_empty_list(self):
        payload = WizardFormPayload(**_minimal())
        assert payload.floorplan_urls == []

    def test_floorplan_urls_single_url(self):
        payload = WizardFormPayload(**_minimal({"floorplan_urls": ["https://example.com/plan.jpg"]}))
        assert payload.floorplan_urls[0] == "https://example.com/plan.jpg"


class TestDeprecatedAndUnwantedFields:
    def test_floorplan_image_url_is_rejected(self):
        """Deprecated singular floorplan_image_url must not be accepted."""
        with pytest.raises(ValidationError):
            WizardFormPayload(**_minimal({"floorplan_image_url": "https://example.com/plan.jpg"}))

    def test_mixed_use_building_type_is_rejected(self):
        """mixed_use is not in the synced frontend contract and must not be accepted."""
        with pytest.raises(ValidationError):
            WizardFormPayload(**_minimal({"building_type": "mixed_use"}))

    def test_unknown_extra_field_is_rejected(self):
        """Extra unknown fields must be rejected (model_config extra=forbid)."""
        with pytest.raises(ValidationError):
            WizardFormPayload(**_minimal({"unknown_field": "some_value"}))
