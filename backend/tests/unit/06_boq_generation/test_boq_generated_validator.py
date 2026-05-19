"""Unit tests for validate_generated_boq_items in boq_validator.py.

Verifies:
- Empty list → is_valid False
- Missing description → error
- Unrecognised category → error
- Missing preferred_unit → warning
- Missing section → warning
- No preliminary items → warning
- Scope conflicts: flat slab + asbestos, normal soil + pile, commercial + domestic, industrial + decorative
- Valid list → is_valid True with no errors
"""
import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from services.validation.boq_validator import validate_generated_boq_items  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _item(
    description="Half brick thick wall in cement and sand 1:4 mortar.",
    category="brick_masonry",
    section="Masonry",
    preferred_unit="m2",
    **extra,
):
    return {"description": description, "category": category,
            "section": section, "preferred_unit": preferred_unit, **extra}

def _prelim():
    return _item(
        description="Contingencies and preliminary works.",
        category="preliminary_and_general",
        section="Preliminaries",
        preferred_unit="item",
    )

def _project(building_type="residential", roof_type="clay_tile", soil_condition="normal", **extra_params):
    params = {"roof_type": roof_type, "soil_condition": soil_condition, **extra_params}
    return {"building_type": building_type, "parameters": params}

# ---------------------------------------------------------------------------
# Structural error tests
# ---------------------------------------------------------------------------

class TestStructuralErrors:
    def test_empty_list_is_invalid(self):
        result = validate_generated_boq_items([], _project())
        assert result["is_valid"] is False
        assert any("empty" in e.lower() for e in result["errors"])

    def test_missing_description_raises_error(self):
        items = [_item(description=""), _prelim()]
        result = validate_generated_boq_items(items, _project())
        assert result["is_valid"] is False
        assert any("missing description" in e for e in result["errors"])

    def test_unrecognised_category_raises_error(self):
        items = [_item(category="made_up_category"), _prelim()]
        result = validate_generated_boq_items(items, _project())
        assert result["is_valid"] is False
        assert any("unrecognised category" in e for e in result["errors"])

    def test_miscellaneous_category_is_valid(self):
        """'miscellaneous' is a valid category (it is in _VALID_CATEGORIES)."""
        items = [_item(category="miscellaneous"), _prelim()]
        result = validate_generated_boq_items(items, _project())
        # Should produce no category errors
        category_errors = [e for e in result["errors"] if "unrecognised category" in e]
        assert category_errors == []

# ---------------------------------------------------------------------------
# Warning-level checks
# ---------------------------------------------------------------------------

# ── BE-TC-033: BOQ validator flags items with missing units ──────────────────

class TestWarnings:
    def test_missing_preferred_unit_produces_warning(self):
        items = [_item(preferred_unit=""), _prelim()]
        result = validate_generated_boq_items(items, _project())
        assert any("preferred_unit" in w for w in result["warnings"])

    def test_missing_section_produces_warning(self):
        items = [_item(section=""), _prelim()]
        result = validate_generated_boq_items(items, _project())
        assert any("section" in w for w in result["warnings"])

    def test_no_preliminary_items_produces_warning(self):
        items = [_item()]  # no preliminary category
        result = validate_generated_boq_items(items, _project())
        assert any("preliminary" in w.lower() for w in result["warnings"])

    def test_has_preliminary_no_completeness_warning(self):
        items = [_item(), _prelim()]
        result = validate_generated_boq_items(items, _project())
        completeness_warnings = [w for w in result["warnings"] if "preliminary" in w.lower()]
        assert completeness_warnings == []

# ---------------------------------------------------------------------------
# Scope conflict rules (Phase 7)
# ---------------------------------------------------------------------------

class TestScopeConflicts:
    def test_flat_slab_with_asbestos_roof_warns(self):
        items = [
            _item(
                description="Supply and fix asbestos cement roofing sheets.",
                category="roofing_and_ceiling",
            ),
            _prelim(),
        ]
        result = validate_generated_boq_items(items, _project(roof_type="flat_slab"))
        assert any("asbestos" in w.lower() for w in result["warnings"])

    def test_flat_slab_no_asbestos_no_warn(self):
        items = [_item(), _prelim()]
        result = validate_generated_boq_items(items, _project(roof_type="flat_slab"))
        asbestos_warnings = [w for w in result["warnings"] if "asbestos" in w.lower()]
        assert asbestos_warnings == []

    def test_normal_soil_with_pile_foundation_warns(self):
        items = [
            _item(
                description="Bored piling 300mm dia including pile cap and pile beam.",
                category="piling_and_substructure",
            ),
            _prelim(),
        ]
        result = validate_generated_boq_items(items, _project(soil_condition="normal"))
        assert any("pile" in w.lower() for w in result["warnings"])

    def test_rocky_soil_pile_does_not_warn(self):
        """Pile items in rocky soil should not trigger the warning."""
        items = [
            _item(
                description="Bored piling 300mm dia including pile cap.",
                category="piling_and_substructure",
            ),
            _prelim(),
        ]
        result = validate_generated_boq_items(items, _project(soil_condition="rocky"))
        pile_warnings = [w for w in result["warnings"] if "pile" in w.lower()]
        assert pile_warnings == []

    def test_commercial_with_bedroom_item_warns(self):
        items = [
            _item(
                description="Supply and fix bedroom wardrobe unit.",
                category="doors_windows_and_glazing",
            ),
            _prelim(),
        ]
        result = validate_generated_boq_items(items, _project(building_type="commercial"))
        assert any("bedroom" in w.lower() or "domestic" in w.lower() for w in result["warnings"])

    def test_residential_bedroom_no_warn(self):
        """Bedroom items in a residential project must not trigger a warning."""
        items = [
            _item(
                description="Supply and fix bedroom wardrobe unit.",
                category="doors_windows_and_glazing",
            ),
            _prelim(),
        ]
        result = validate_generated_boq_items(items, _project(building_type="residential"))
        bedroom_warnings = [w for w in result["warnings"] if "bedroom" in w.lower()]
        assert bedroom_warnings == []

    def test_industrial_decorative_tile_warns(self):
        items = [
            _item(
                description="Supply and fix decorative ceramic floor tiles 300x300mm.",
                category="flooring_and_tiling",
            ),
            _prelim(),
        ]
        result = validate_generated_boq_items(items, _project(building_type="industrial"))
        assert any("decorative" in w.lower() for w in result["warnings"])

    def test_industrial_plain_tile_does_not_warn(self):
        """Non-decorative industrial floor tile should not trigger a warning."""
        items = [
            _item(
                description="Supply and fix heavy-duty industrial epoxy floor coating.",
                category="flooring_and_tiling",
            ),
            _prelim(),
        ]
        result = validate_generated_boq_items(items, _project(building_type="industrial"))
        decorative_warnings = [w for w in result["warnings"] if "decorative" in w.lower()]
        assert decorative_warnings == []

# ---------------------------------------------------------------------------
# Happy-path test
# ---------------------------------------------------------------------------

class TestValidList:
    def test_fully_valid_list_passes(self):
        items = [
            _item(),
            _item(
                description="Volume batched Grade 30 concrete in ground floor slab.",
                category="concrete_works",
                section="Concrete Works",
                preferred_unit="m3",
            ),
            _prelim(),
        ]
        result = validate_generated_boq_items(items, _project(soil_condition="normal"))
        assert result["is_valid"] is True
        assert result["errors"] == []
