"""Unit tests for build_final_boq_items in boq_builder.py.

Verifies:
- Stage order: LLM baseline (standalone, no predictor seeds) → Item Predictor → LLM gap-fill
- Provenance tags: llm_baseline, llm_reconciled
- baseline runs independently without predictor hints
- Graceful degradation when any stage fails
"""
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

# ---------------------------------------------------------------------------
# Stub out heavy / unavailable transitive dependencies before importing
# boq_builder (which imports llm_client → ollama_client).
# ---------------------------------------------------------------------------
def _make_stub(name: str) -> ModuleType:
    mod = ModuleType(name)
    mod.__spec__ = None  # type: ignore[attr-defined]
    return mod

for _name in ("openai", "openai.types", "openai.types.chat"):
    if _name not in sys.modules:
        sys.modules[_name] = _make_stub(_name)

# Stub the chat function used by llm_client
_oc_stub = _make_stub("infrastructure.integrations.ollama_client")
_oc_stub.chat = MagicMock(return_value="{}")  # type: ignore[attr-defined]
sys.modules.setdefault("infrastructure.integrations.ollama_client", _oc_stub)

# Stub joblib / sklearn so item_predictor can be imported too
for _name in ("joblib", "sklearn", "sklearn.ensemble", "numpy", "numpy.core"):
    if _name not in sys.modules:
        sys.modules[_name] = _make_stub(_name)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_project_info(building_type="residential", floors=1):
    return {
        "building_type": building_type,
        "floors": floors,
        "parameters": {"built_up_area": "167 m2", "roof_type": "clay_tile"},
    }

def _make_raw_items(descriptions, category="concrete_works"):
    return [
        {"description": d, "category": category, "section": "Concrete Works"}
        for d in descriptions
    ]

# ---------------------------------------------------------------------------
# Stage-order and provenance tests
# ---------------------------------------------------------------------------

class TestBuildFinalBoqItemsStageOrder:
    """Verify stage order: LLM baseline (standalone) → Item Predictor → LLM gap-fill."""

    def test_baseline_called_before_predictor(self):
        """generate_baseline_boq must be called BEFORE predict_boq_items_with_confidence."""
        call_order: list[str] = []

        def fake_baseline(pi):
            call_order.append("baseline")
            return _make_raw_items(["Concrete in foundations"])

        def fake_predictor(pi):
            call_order.append("predictor")
            return [{"description": "Concrete in foundations", "source_confidence": 0.8}]

        def fake_reconcile(pi, baseline, predictor):
            call_order.append("reconcile")
            return _make_raw_items(["Concrete in foundations"])

        from services.item_gen_process.boq_builder import build_final_boq_items

        with (
            patch("services.item_gen_process.boq_builder.generate_baseline_boq", side_effect=fake_baseline),
            patch("services.item_gen_process.boq_builder.predict_boq_items_with_confidence", side_effect=fake_predictor),
            patch("services.item_gen_process.boq_builder.gap_fill_boq_items", side_effect=fake_reconcile),
        ):
            build_final_boq_items(_make_project_info())

        assert call_order == ["baseline", "predictor", "reconcile"], (
            f"Expected baseline → predictor → reconcile, got {call_order}"
        )

    def test_baseline_receives_no_predictor_hints(self):
        """generate_baseline_boq must be called without item_predictor_hints (independent pass)."""
        captured_kwargs: dict = {}

        def fake_baseline(pi, **kwargs):
            captured_kwargs.update(kwargs)
            return _make_raw_items(["Foundation concrete"])

        with (
            patch("services.item_gen_process.boq_builder.generate_baseline_boq", side_effect=fake_baseline),
            patch("services.item_gen_process.boq_builder.predict_boq_items_with_confidence",
                  return_value=[{"description": "Foundation concrete", "source_confidence": 0.8}]),
            patch("services.item_gen_process.boq_builder.gap_fill_boq_items",
                  return_value=_make_raw_items(["Foundation concrete"])),
        ):
            from services.item_gen_process.boq_builder import build_final_boq_items
            build_final_boq_items(_make_project_info())

        # Baseline must not receive any predictor hints — it runs independently
        assert captured_kwargs.get("item_predictor_hints") is None, (
            "generate_baseline_boq must not receive predictor hints in the aligned flow."
        )

    def test_reconcile_receives_predictor_descriptions_only(self):
        """gap_fill_boq_items must receive only the description strings from predictor output."""
        captured_predictor_arg: dict = {}

        def fake_reconcile(pi, baseline, predictor):
            captured_predictor_arg["value"] = predictor
            return _make_raw_items(["Foundation concrete", "Staircase balustrade"])

        with (
            patch("services.item_gen_process.boq_builder.predict_boq_items_with_confidence",
                  return_value=[{"description": "Staircase balustrade", "source_confidence": 0.72}]),
            patch("services.item_gen_process.boq_builder.generate_baseline_boq",
                  return_value=_make_raw_items(["Foundation concrete"])),
            patch("services.item_gen_process.boq_builder.gap_fill_boq_items", side_effect=fake_reconcile),
        ):
            from services.item_gen_process.boq_builder import build_final_boq_items
            build_final_boq_items(_make_project_info())

        assert captured_predictor_arg["value"] == ["Staircase balustrade"]

# ---------------------------------------------------------------------------
# Provenance / source tagging tests
# ---------------------------------------------------------------------------

class TestProvenanceTags:
    """Verify source field values on items returned by build_final_boq_items."""

    def _run(self, reconciled_descriptions, predictor_addition_descriptions=None):
        """Helper: mock all three stages and return the enriched final items."""
        predictor_items = [
            {"description": d, "source_confidence": 0.70}
            for d in (predictor_addition_descriptions or [])
        ]
        reconciled = [
            {"description": d, "category": "concrete_works", "section": "Concrete"}
            for d in reconciled_descriptions
        ]

        with (
            patch("services.item_gen_process.boq_builder.predict_boq_items_with_confidence",
                  return_value=predictor_items),
            patch("services.item_gen_process.boq_builder.generate_baseline_boq",
                  return_value=_make_raw_items(["Foundation concrete"])),
            patch("services.item_gen_process.boq_builder.gap_fill_boq_items",
                  return_value=reconciled),
        ):
            from services.item_gen_process.boq_builder import build_final_boq_items
            return build_final_boq_items(_make_project_info())

    def test_items_without_source_tagged_llm_reconciled(self):
        """Items returned from gap_fill_boq_items without an existing source tag
        must receive source='llm_reconciled'."""
        items = self._run(["Foundation concrete", "Brick masonry work"])
        sources = {item["description"]: item.get("source") for item in items}
        assert sources.get("Foundation concrete") == "llm_reconciled"
        assert sources.get("Brick masonry work") == "llm_reconciled"

    def test_empty_predictor_additions_still_produces_items(self):
        """Pipeline must complete successfully even if predictor returns no additions."""
        items = self._run(["Foundation concrete"], predictor_addition_descriptions=[])
        assert len(items) >= 1

# ---------------------------------------------------------------------------
# Graceful degradation
# ---------------------------------------------------------------------------

class TestGracefulDegradation:
    def test_predictor_failure_falls_through_to_reconciliation(self):
        """If predict_boq_items_with_confidence raises, pipeline continues with empty hints."""
        def boom(pi):
            raise RuntimeError("predictor exploded")

        with (
            patch("services.item_gen_process.boq_builder.predict_boq_items_with_confidence",
                  side_effect=boom),
            patch("services.item_gen_process.boq_builder.generate_baseline_boq",
                  return_value=_make_raw_items(["Foundation concrete"])),
            patch("services.item_gen_process.boq_builder.gap_fill_boq_items",
                  return_value=_make_raw_items(["Foundation concrete"])),
        ):
            from services.item_gen_process.boq_builder import build_final_boq_items
            items = build_final_boq_items(_make_project_info())

        assert len(items) >= 1

    def test_reconciliation_failure_falls_back_to_baseline(self):
        """If gap_fill_boq_items raises, pipeline should fall back to baseline items."""
        def boom(pi, baseline, predictor):
            raise RuntimeError("reconciliation exploded")

        with (
            patch("services.item_gen_process.boq_builder.predict_boq_items_with_confidence",
                  return_value=[]),
            patch("services.item_gen_process.boq_builder.generate_baseline_boq",
                  return_value=_make_raw_items(["Foundation concrete"])),
            patch("services.item_gen_process.boq_builder.gap_fill_boq_items",
                  side_effect=boom),
        ):
            from services.item_gen_process.boq_builder import build_final_boq_items
            items = build_final_boq_items(_make_project_info())

        descriptions = {item["description"] for item in items}
        assert "Foundation concrete" in descriptions
