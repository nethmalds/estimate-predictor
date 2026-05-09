"""Unit tests for _apply_rules in item_predictor.py."""
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from services.item_gen_process.item_predictor import _apply_rules  # noqa: E402


# ── Helpers ────────────────────────────────────────────────────────────────────

def _project(building_type="residential", floors=1, roof_type="clay_tile", **extra_params):
    params = {"roof_type": roof_type, **extra_params}
    return {
        "building_type": building_type,
        "floors": floors,
        "parameters": params,
    }


# ── Universal rules ────────────────────────────────────────────────────────────

class TestUniversalRules:
    def test_staircase_added_for_multi_floor(self):
        items = _apply_rules(_project(floors=2), set())
        assert "staircase work" in items

    def test_staircase_not_added_for_single_floor(self):
        items = _apply_rules(_project(floors=1), set())
        assert "staircase work" not in items

    def test_waterproofing_added_for_flat_slab(self):
        items = _apply_rules(_project(roof_type="rc_flat_slab"), set())
        assert "waterproofing work" in items

    def test_waterproofing_added_for_slab_keyword(self):
        items = _apply_rules(_project(roof_type="flat slab"), set())
        assert "waterproofing work" in items

    def test_waterproofing_not_added_for_clay_tile(self):
        items = _apply_rules(_project(roof_type="clay tile"), set())
        assert "waterproofing work" not in items


# ── Commercial rules ───────────────────────────────────────────────────────────

class TestCommercialRules:
    def test_washroom_fitout_always_added_for_commercial(self):
        items = _apply_rules(_project("commercial", primary_use_type="Office", washroom_count=2), set())
        assert "commercial toilet / washroom fit-out" in items

    def test_restaurant_adds_kitchen_exhaust(self):
        items = _apply_rules(_project("commercial", primary_use_type="restaurant", washroom_count=2), set())
        assert "commercial kitchen exhaust and ventilation" in items
        assert "grease trap and drainage" in items

    def test_food_beverage_adds_kitchen_items(self):
        items = _apply_rules(_project("commercial", primary_use_type="food & beverage", washroom_count=2), set())
        assert "commercial kitchen exhaust and ventilation" in items

    def test_hotel_adds_elevator(self):
        items = _apply_rules(_project("commercial", primary_use_type="hotel", washroom_count=2), set())
        assert "elevator / lift installation" in items

    def test_office_does_not_add_elevator(self):
        items = _apply_rules(_project("commercial", primary_use_type="office", washroom_count=2), set())
        assert "elevator / lift installation" not in items

    def test_many_washrooms_adds_plumbing_riser(self):
        items = _apply_rules(_project("commercial", primary_use_type="Office", washroom_count=4), set())
        assert "centralised plumbing riser and distribution" in items

    def test_few_washrooms_no_plumbing_riser(self):
        items = _apply_rules(_project("commercial", primary_use_type="Office", washroom_count=2), set())
        assert "centralised plumbing riser and distribution" not in items


# ── Industrial rules ───────────────────────────────────────────────────────────

class TestIndustrialRules:
    def test_heavy_machinery_adds_reinforced_slab(self):
        items = _apply_rules(_project("industrial", heavy_machinery_load="yes"), set())
        assert "heavy-duty industrial floor slab" in items
        assert "reinforced foundation for machinery" in items

    def test_no_heavy_machinery_no_slab(self):
        items = _apply_rules(_project("industrial", heavy_machinery_load="no"), set())
        assert "heavy-duty industrial floor slab" not in items

    def test_hazardous_materials_adds_fire_suppression(self):
        items = _apply_rules(_project("industrial", hazardous_materials="yes"), set())
        assert "fire suppression system" in items
        assert "chemical-resistant floor coating" in items
        assert "hazardous material containment bund" in items

    def test_no_hazardous_no_fire_suppression(self):
        items = _apply_rules(_project("industrial", hazardous_materials="no"), set())
        assert "fire suppression system" not in items

    def test_specialized_ventilation_adds_fume_extraction(self):
        items = _apply_rules(_project("industrial", specialized_ventilation="yes"), set())
        assert "industrial fume extraction system" in items
        assert "dust collection and filtration unit" in items

    def test_no_ventilation_no_fume_system(self):
        items = _apply_rules(_project("industrial", specialized_ventilation="no"), set())
        assert "industrial fume extraction system" not in items

    def test_cold_storage_adds_cold_room_panels(self):
        items = _apply_rules(_project("industrial", facility_type="Cold Storage Facility"), set())
        assert "cold room insulated panel system" in items
        assert "refrigeration plant room" in items

    def test_factory_does_not_add_cold_room(self):
        items = _apply_rules(_project("industrial", facility_type="Factory / Manufacturing"), set())
        assert "cold room insulated panel system" not in items


# ── Cross-contamination guard ──────────────────────────────────────────────────

class TestCrossContamination:
    def test_residential_does_not_get_commercial_items(self):
        items = _apply_rules(_project("residential", floors=1), set())
        assert "commercial toilet / washroom fit-out" not in items

    def test_residential_does_not_get_industrial_items(self):
        items = _apply_rules(_project("residential", floors=1), set())
        assert "heavy-duty industrial floor slab" not in items
        assert "fire suppression system" not in items
