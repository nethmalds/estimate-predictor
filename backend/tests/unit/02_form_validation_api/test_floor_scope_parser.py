"""Unit tests for the shared floor-scope parsing helpers.

Covers parse_floor_scope, strip_scope_tokens, and normalize_floor_label —
used by both item_gen and quantity_gen services.
"""
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from services.shared.floor_scope import (  # noqa: E402
    normalize_floor_label,
    parse_floor_scope,
    strip_scope_tokens,
)


class TestParseFloorScope:
    def test_canonical_ground_floor(self):
        assert parse_floor_scope("Brick masonry in ground floor") == "ground"

    def test_canonical_first_floor(self):
        assert parse_floor_scope("Plastering on first floor walls") == "first"

    def test_canonical_higher_floors(self):
        assert parse_floor_scope("Concrete in second floor") == "second"
        assert parse_floor_scope("Flooring tiles third floor") == "third"

    def test_basement_and_roof(self):
        assert parse_floor_scope("Excavation for basement walls") == "basement"
        assert parse_floor_scope("Roof tile fixing") == "roof"

    def test_alias_gf(self):
        assert parse_floor_scope("Brick masonry GF external walls") == "ground"

    def test_alias_ff(self):
        assert parse_floor_scope("FF internal partitions") == "first"

    def test_alias_sf(self):
        assert parse_floor_scope("SF concrete slab") == "second"

    def test_no_floor_token_returns_all(self):
        assert parse_floor_scope("Preliminary and general items") == "all"
        assert parse_floor_scope("Roof tile ridge") == "roof"  # but "roof" matches

    def test_truly_floorless_description(self):
        assert parse_floor_scope("Site clearing including bushes") == "all"

    def test_empty_description(self):
        assert parse_floor_scope("") == "all"
        assert parse_floor_scope(None) == "all"  # type: ignore[arg-type]

    def test_case_insensitive(self):
        assert parse_floor_scope("FIRST FLOOR brickwork") == "first"
        assert parse_floor_scope("Ground Floor plastering") == "ground"

    def test_first_match_wins_when_multiple_tokens(self):
        # Embedded second token shouldn't override the first
        assert parse_floor_scope("ground floor and first floor walls") == "ground"


class TestStripScopeTokens:
    def test_strips_floor_token(self):
        result = strip_scope_tokens("Brick masonry in ground floor")
        assert "ground" not in result
        assert "brick masonry" in result

    def test_strips_thickness_tokens(self):
        result = strip_scope_tokens('9" brick wall in cement and sand 1:5')
        assert "9" not in result.split()
        assert "brick wall" in result

    def test_strips_orientation_tokens(self):
        result = strip_scope_tokens("External walls plastering")
        assert "external" not in result
        assert "walls plastering" in result

    def test_groups_floor_and_wall_variants_to_same_signature(self):
        sig_a = strip_scope_tokens("Brick masonry 1:5 external walls ground floor")
        sig_b = strip_scope_tokens("Brick masonry 1:5 internal partition walls first floor")
        # Different in floor + orientation only — same signature after strip.
        # Note: "partition" gets stripped too.
        assert sig_a == sig_b

    def test_empty_input(self):
        assert strip_scope_tokens("") == ""
        assert strip_scope_tokens(None) == ""  # type: ignore[arg-type]

    def test_normalises_punctuation_and_whitespace(self):
        result = strip_scope_tokens("Concrete, grade 25 — in first floor.")
        assert "  " not in result  # collapsed whitespace
        assert "first" not in result


class TestNormalizeFloorLabel:
    def test_canonical_label(self):
        assert normalize_floor_label("Ground Floor", index=0) == "ground"
        assert normalize_floor_label("First Floor", index=1) == "first"

    def test_alias_label(self):
        assert normalize_floor_label("GF", index=0) == "ground"
        assert normalize_floor_label("FF", index=1) == "first"

    def test_ambiguous_label_falls_back_to_index(self):
        # "Floor 1" has no canonical token → use index 0 → ground
        assert normalize_floor_label("Floor 1", index=0) == "ground"
        assert normalize_floor_label("Top Level", index=2) == "second"

    def test_empty_label_falls_back_to_index(self):
        assert normalize_floor_label("", index=0) == "ground"
        assert normalize_floor_label("", index=3) == "third"

    def test_high_index_returns_level_n(self):
        assert normalize_floor_label("", index=15) == "level_15"
