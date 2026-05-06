"""Unit tests for normalize_wizard_to_project_info in clarification_agent.py."""
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from services.clarification_process.clarification_agent import normalize_wizard_to_project_info  # noqa: E402


# ── Helpers ────────────────────────────────────────────────────────────────────

def _floor_area(value=200.0, unit="m2"):
    return [{"floor_label": "Ground Floor", "area_value": value, "area_unit": unit}]


def _base(building_type="residential", overrides=None):
    payload = {
        "building_type": building_type,
        "floor_count": 2,
        "floor_areas": _floor_area(),
        "bedrooms": 3,
        "bathrooms": 2,
        "finish_level": "standard",
        "structural_system": "framed",
        "roof_type": "rc_flat_slab",
        "ceiling_type": "gypsum_mineral_fibre",
        "location": "Colombo",
        "soil_condition": "normal",
        "drainage_type": "mains_sewer",
        "external_works_scope": "standard",
    }
    if overrides:
        payload.update(overrides)
    return payload


# ── Residential normalization ──────────────────────────────────────────────────

class TestResidentialNormalization:
    def test_bedrooms_in_parameters(self):
        result = normalize_wizard_to_project_info(_base())
        assert result["parameters"]["bedrooms"] == 3

    def test_bathrooms_in_parameters(self):
        result = normalize_wizard_to_project_info(_base())
        assert result["parameters"]["bathrooms"] == 2

    def test_building_type_set_correctly(self):
        result = normalize_wizard_to_project_info(_base())
        assert result["building_type"] == "residential"

    def test_floors_set_from_floor_count(self):
        result = normalize_wizard_to_project_info(_base())
        assert result["floors"] == 2


# ── Commercial normalization ───────────────────────────────────────────────────

class TestCommercialNormalization:
    def test_primary_use_type_in_parameters(self):
        result = normalize_wizard_to_project_info(_base("commercial", {
            "primary_use_type": "Office",
            "washroom_count": 4,
        }))
        assert result["parameters"]["primary_use_type"] == "Office"

    def test_washroom_count_in_parameters(self):
        result = normalize_wizard_to_project_info(_base("commercial", {
            "primary_use_type": "Retail",
            "washroom_count": 2,
        }))
        assert result["parameters"]["washroom_count"] == 2

    def test_commercial_does_not_get_residential_fields(self):
        result = normalize_wizard_to_project_info(_base("commercial", {
            "primary_use_type": "Office",
            "washroom_count": 2,
        }))
        assert "bedrooms" not in result["parameters"]
        assert "bathrooms" not in result["parameters"]


# ── Industrial normalization ───────────────────────────────────────────────────

class TestIndustrialNormalization:
    def _industrial_payload(self):
        return _base("industrial", {
            "facility_type": "Factory / Manufacturing",
            "heavy_machinery_load": "yes",
            "hazardous_materials": "yes",
            "specialized_ventilation": "no",
        })

    def test_facility_type_in_parameters(self):
        result = normalize_wizard_to_project_info(self._industrial_payload())
        assert result["parameters"]["facility_type"] == "Factory / Manufacturing"

    def test_heavy_machinery_load_in_parameters(self):
        result = normalize_wizard_to_project_info(self._industrial_payload())
        assert result["parameters"]["heavy_machinery_load"] == "yes"

    def test_hazardous_materials_in_parameters(self):
        result = normalize_wizard_to_project_info(self._industrial_payload())
        assert result["parameters"]["hazardous_materials"] == "yes"

    def test_specialized_ventilation_in_parameters(self):
        result = normalize_wizard_to_project_info(self._industrial_payload())
        assert result["parameters"]["specialized_ventilation"] == "no"

    def test_industrial_does_not_get_residential_fields(self):
        result = normalize_wizard_to_project_info(self._industrial_payload())
        assert "bedrooms" not in result["parameters"]


# ── QS fields should NOT be in output from wizard route ───────────────────────

class TestQSFieldsAbsent:
    def test_qs_specifications_empty_from_wizard(self):
        """Wizard route must not populate qs_specifications."""
        result = normalize_wizard_to_project_info(_base())
        qs = result.get("qs_specifications", {})
        assert qs == {}

    def test_no_construction_scope_in_output(self):
        result = normalize_wizard_to_project_info(_base())
        assert "construction_scope" not in result.get("qs_specifications", {})


# ── Floor area calculation ─────────────────────────────────────────────────────

class TestFloorAreaCalculation:
    def test_single_m2_floor_area(self):
        payload = _base(overrides={"floor_areas": [
            {"floor_label": "Ground Floor", "area_value": 150.0, "area_unit": "m2"},
        ]})
        result = normalize_wizard_to_project_info(payload)
        params = result["parameters"]
        # built_up_area in m2 or sqft — just ensure it's present and positive
        area_raw = params.get("built_up_area") or params.get("built_up_area_m2", "0")
        assert float(str(area_raw).split()[0]) > 0

    def test_sqft_floor_area_converted(self):
        payload = _base(overrides={"floor_areas": [
            {"floor_label": "Ground Floor", "area_value": 1000.0, "area_unit": "sqft"},
        ]})
        result = normalize_wizard_to_project_info(payload)
        params = result["parameters"]
        area_raw = params.get("built_up_area") or params.get("built_up_area_m2", "0")
        assert float(str(area_raw).split()[0]) > 0


# ── Provenance and defaults semantics ─────────────────────────────────────────

class TestProvenanceSemantics:
    def test_applied_defaults_empty_after_normalize(self):
        """normalize_wizard_to_project_info must not pre-fill any defaults.
        All defaults should be applied only by apply_defaults()."""
        result = normalize_wizard_to_project_info(_base())
        assert result["applied_defaults"] == []

    def test_user_provided_fields_in_explicit_parameters(self):
        """Fields explicitly set by the user must appear in explicit_parameters."""
        result = normalize_wizard_to_project_info(_base())
        explicit = result["explicit_parameters"]
        assert "finish_level" in explicit
        assert "structural_system" in explicit
        assert "roof_type" in explicit
        assert "ceiling_type" in explicit

    def test_omitted_optional_field_not_in_explicit_parameters(self):
        """A field not provided by the user must NOT appear in explicit_parameters
        and must be None in parameters, so apply_defaults() can fill it."""
        payload = _base(overrides={"location": None, "soil_condition": None})
        result = normalize_wizard_to_project_info(payload)
        assert "location" not in result["explicit_parameters"]
        assert "soil_condition" not in result["explicit_parameters"]
        assert result["parameters"]["location"] is None
        assert result["parameters"]["soil_condition"] is None

    def test_user_provided_fields_marked_as_user_in_value_sources(self):
        """All user-supplied fields must appear in value_sources as 'user'."""
        result = normalize_wizard_to_project_info(_base())
        sources = result["value_sources"]
        assert sources.get("finish_level") == "user"
        assert sources.get("structural_system") == "user"

    def test_omitted_field_absent_from_value_sources(self):
        """Fields not provided must not be marked as 'user' in value_sources."""
        payload = _base(overrides={"drainage_type": None, "external_works_scope": None})
        result = normalize_wizard_to_project_info(payload)
        sources = result["value_sources"]
        assert "drainage_type" not in sources
        assert "external_works_scope" not in sources
