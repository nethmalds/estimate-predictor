"""Unit tests for the RAG candidate scoring function.

score_candidate() is a pure function — no external dependencies needed.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from services.rag_process.retriever import QueryFeatures  # noqa: E402
from services.rag_process.scorer import score_candidate  # noqa: E402


def _features(
    normalized_text: str = "brick masonry wall",
    tokens: list[str] | None = None,
    work_type: str | None = "masonry",
    material: str | None = "brick",
    method: str | None = None,
    constraints: list[str] | None = None,
) -> QueryFeatures:
    return QueryFeatures(
        normalized_text=normalized_text,
        tokens=tokens or normalized_text.split(),
        work_type=work_type,
        material=material,
        method=method,
        constraints=constraints or [],
    )


def _candidate(
    description: str = "brick masonry wall construction",
    work_type: str | None = "masonry",
    method: str | None = None,
    constraints: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        description=description,
        work_type=work_type,
        method=method,
        constraints=constraints,
    )


# ── BE-TC-038 & 039: RAG scorer — work type scoring and bounded confidence ────

class TestScoreCandidate:
    def test_returns_required_keys(self):
        result = score_candidate(_features(), _candidate(), vector_score=0.8)
        for key in ("vector_score", "keyword_score", "final_score", "matched_fields"):
            assert key in result

    def test_material_match_increases_keyword_score(self):
        with_match = score_candidate(
            _features(material="brick"),
            _candidate(description="brick masonry wall"),
            vector_score=0.5,
        )
        without_match = score_candidate(
            _features(material="brick"),
            _candidate(description="concrete beam column"),
            vector_score=0.5,
        )
        assert with_match["keyword_score"] > without_match["keyword_score"]

    def test_material_match_appears_in_matched_fields(self):
        result = score_candidate(
            _features(material="brick"),
            _candidate(description="brick masonry wall"),
            vector_score=0.5,
        )
        assert any("material" in f for f in result["matched_fields"])

    def test_work_type_match_appears_in_matched_fields(self):
        result = score_candidate(
            _features(work_type="masonry"),
            _candidate(work_type="masonry"),
            vector_score=0.5,
        )
        assert any("work_type" in f for f in result["matched_fields"])

    def test_method_match_appears_in_matched_fields(self):
        result = score_candidate(
            _features(method="ready-mix"),
            _candidate(method="ready-mix", description="ready-mix concrete"),
            vector_score=0.5,
        )
        assert any("method" in f for f in result["matched_fields"])

    def test_final_score_is_weighted_combination(self):
        vector_score = 0.8
        result = score_candidate(
            _features(material=None, work_type=None),
            _candidate(description="unrelated item"),
            vector_score=vector_score,
        )
        # With zero keyword score, final ≈ vector_weight * vector_score (0.65 * 0.8 = 0.52)
        assert abs(result["final_score"] - 0.65 * vector_score) < 0.05

    def test_final_score_bounded_between_zero_and_one(self):
        result = score_candidate(
            _features(material="brick", work_type="masonry", method="manual"),
            _candidate(
                description="brick masonry manual work brick",
                work_type="masonry",
                method="manual",
            ),
            vector_score=1.0,
        )
        assert 0.0 <= result["final_score"] <= 1.0

    def test_no_matches_produces_empty_matched_fields(self):
        result = score_candidate(
            _features(material=None, work_type=None, method=None, tokens=[], constraints=[]),
            _candidate(description="xyz abc", work_type=None, method=None),
            vector_score=0.5,
        )
        assert result["matched_fields"] == []

    def test_scores_are_rounded_to_four_decimal_places(self):
        result = score_candidate(_features(), _candidate(), vector_score=0.123456789)
        assert len(str(result["final_score"]).split(".")[-1]) <= 4

    def test_custom_weights_alter_final_score(self):
        result_default = score_candidate(
            _features(material="brick"),
            _candidate(description="brick masonry"),
            vector_score=0.7,
        )
        result_keyword_heavy = score_candidate(
            _features(material="brick"),
            _candidate(description="brick masonry"),
            vector_score=0.7,
            vector_weight=0.2,
            keyword_weight=0.8,
        )
        assert result_keyword_heavy["final_score"] != result_default["final_score"]
