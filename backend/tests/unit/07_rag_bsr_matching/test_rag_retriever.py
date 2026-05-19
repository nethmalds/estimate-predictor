"""Unit tests for pure retriever functions in services.rag_process.retriever.

Only the stateless helper functions are tested here — no Chroma, no DB, no
embedding model. The heavy infrastructure imports in retriever.py are all lazy
(only triggered when retrieve_candidates() is called), so importing the module
does not require mocking chromadb.
"""
import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from services.rag_process.retriever import (  # noqa: E402
    clean_boq_query,
    extract_query_features,
    normalize_query,
)


# ── BE-TC-037: Query normalisation lowercases and strips special characters ───

class TestNormalizeQuery:
    def test_lowercases_input(self):
        assert normalize_query("Excavation Work") == "excavation work"

    def test_strips_special_chars(self):
        result = normalize_query("brick masonry @ 1:4 ratio!")
        assert "@" not in result
        assert "!" not in result

    def test_collapses_whitespace(self):
        result = normalize_query("  brick   masonry  ")
        assert result == "brick masonry"

    def test_preserves_hyphens_and_slashes(self):
        result = normalize_query("ready-mix concrete m20/m25")
        assert "-" in result
        assert "/" in result

    def test_empty_string_returns_empty(self):
        assert normalize_query("") == ""


class TestCleanBoqQuery:
    def test_removes_supply_and_fix_prefix(self):
        result = clean_boq_query("supply and fix ceramic floor tiles")
        assert not result.startswith("supply")

    def test_removes_numeric_nos_prefix(self):
        result = clean_boq_query("5 nos. door frames")
        assert not result.startswith("5")

    def test_removes_combined_prefix(self):
        result = clean_boq_query("supply and fix 3 nos. window frames")
        assert "window frames" in result
        assert not result.startswith("supply")

    def test_leaves_plain_description_unchanged(self):
        result = clean_boq_query("concrete M20 grade")
        assert "concrete" in result

    def test_strips_result(self):
        result = clean_boq_query("  supply and fix  ceramic tiles  ")
        assert not result.startswith(" ")


class TestExtractQueryFeatures:
    def test_identifies_masonry_work_type(self):
        features = extract_query_features("brick masonry wall construction")
        assert features.work_type == "masonry"

    def test_identifies_excavation_work_type(self):
        features = extract_query_features("excavation of foundation trenches")
        assert features.work_type == "excavation"

    def test_identifies_concrete_work_type(self):
        features = extract_query_features("concrete M20 grade column")
        assert features.work_type == "concrete"

    def test_identifies_m25_material(self):
        features = extract_query_features("concrete m25 grade beam")
        assert features.material == "m25"

    def test_identifies_brick_material(self):
        features = extract_query_features("brick wall half-brick thick")
        assert features.material == "brick"

    def test_identifies_ready_mix_method(self):
        features = extract_query_features("ready-mix concrete delivery")
        assert features.method == "ready-mix"

    def test_extracts_depth_constraint(self):
        features = extract_query_features("excavation to depth of 1.5m")
        assert any("depth" in c for c in features.constraints)

    def test_extracts_size_constraint(self):
        features = extract_query_features("brickwork 230x115mm")
        assert any("size" in c for c in features.constraints)

    def test_filters_noise_words_from_tokens(self):
        features = extract_query_features("the concrete and the masonry")
        assert "the" not in features.tokens
        assert "and" not in features.tokens

    def test_returns_none_when_no_work_type(self):
        features = extract_query_features("project management services")
        assert features.work_type is None

    def test_normalized_text_is_lowercase(self):
        features = extract_query_features("BRICK MASONRY WORK")
        assert features.normalized_text == features.normalized_text.lower()
