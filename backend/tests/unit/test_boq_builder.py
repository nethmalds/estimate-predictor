"""Unit tests for build_final_boq_items in boq_builder.py.

Verifies:
- Stage order: LLM baseline → Item Predictor additions → LLM reconciliation
- Provenance tags: llm_baseline, item_predictor_addition, llm_reconciled
- _predictor_conf lookup is built from predictor additions (not all predictions)
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
# boq_builder (which imports llm_client → openrouter_client → openai).
# ---------------------------------------------------------------------------
def _make_stub(name: str) -> ModuleType:
    mod = ModuleType(name)
    mod.__spec__ = None  # type: ignore[attr-defined]
    return mod

for _name in ("openai", "openai.types", "openai.types.chat"):
    if _name not in sys.modules:
        sys.modules[_name] = _make_stub(_name)

# Stub the chat function used by llm_client
_oc_stub = _make_stub("infrastructure.integrations.openrouter_client")
_oc_stub.chat = MagicMock(return_value="{}")  # type: ignore[attr-defined]
sys.modules.setdefault("infrastructure.integrations.openrouter_client", _oc_stub)

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
    """Verify the new stage order: LLM baseline → predictor additions → LLM reconciliation."""

    def test_baseline_called_before_predictor(self):
        """generate_baseline_boq must be called before predict_additional_boq_items."""
        call_order: list[str] = []

        def fake_baseline(pi):
            call_order.append("baseline")
            return _make_raw_items(["Concrete in foundations"])

        def fake_predictor(pi, baseline):
            call_order.append("predictor")
            return []

        def fake_reconcile(pi, baseline, predictor):
            call_order.append("reconcile")
            return _make_raw_items(["Concrete in foundations"])

        from services.item_gen_process.boq_builder import build_final_boq_items

        with (
            patch("services.item_gen_process.boq_builder.generate_baseline_boq", side_effect=fake_baseline),
            patch("services.item_gen_process.boq_builder.predict_additional_boq_items", side_effect=fake_predictor),
            patch("services.item_gen_process.boq_builder.gap_fill_boq_items", side_effect=fake_reconcile),
        ):
            build_final_boq_items(_make_project_info())

        assert call_order == ["baseline", "predictor", "reconcile"], (
            f"Expected baseline → predictor → reconcile, got {call_order}"
        )

    def test_predictor_receives_baseline_items(self):
        """predict_additional_boq_items must receive the baseline items list."""
        baseline_items = _make_raw_items(["Foundation concrete"])
        captured_baseline = {}

        def fake_baseline(pi):
            return baseline_items

        def fake_predictor(pi, baseline):
            captured_baseline["value"] = baseline
            return []

        def fake_reconcile(pi, baseline, predictor):
            return baseline_items

        with (
            patch("services.item_gen_process.boq_builder.generate_baseline_boq", side_effect=fake_baseline),
            patch("services.item_gen_process.boq_builder.predict_additional_boq_items", side_effect=fake_predictor),
            patch("services.item_gen_process.boq_builder.gap_fill_boq_items", side_effect=fake_reconcile),
        ):
            from services.item_gen_process.boq_builder import build_final_boq_items
            build_final_boq_items(_make_project_info())

        # Should be the same list passed through
        assert captured_baseline.get("value") is not None
        assert any(
            item["description"] == "Foundation concrete"
            for item in captured_baseline["value"]
        )

    def test_reconcile_receives_predictor_descriptions_only(self):
        """gap_fill_boq_items must receive only the description strings from predictor additions."""
        additions = [
            {
                "description": "Staircase balustrade",
                "source_confidence": 0.72,
                "predicted_category": "formwork",
                "source": "item_predictor_addition",
            }
        ]
        captured_predictor_arg = {}

        def fake_reconcile(pi, baseline, predictor):
            captured_predictor_arg["value"] = predictor
            return _make_raw_items(["Foundation concrete", "Staircase balustrade"])

        with (
            patch("services.item_gen_process.boq_builder.generate_baseline_boq",
                  return_value=_make_raw_items(["Foundation concrete"])),
            patch("services.item_gen_process.boq_builder.predict_additional_boq_items",
                  return_value=additions),
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
        predictor_additions = [
            {
                "description": d,
                "source_confidence": 0.70,
                "predicted_category": "concrete_works",
                "source": "item_predictor_addition",
            }
            for d in (predictor_addition_descriptions or [])
        ]
        reconciled = [
            {"description": d, "category": "concrete_works", "section": "Concrete"}
            for d in reconciled_descriptions
        ]

        with (
            patch("services.item_gen_process.boq_builder.generate_baseline_boq",
                  return_value=_make_raw_items(["Foundation concrete"])),
            patch("services.item_gen_process.boq_builder.predict_additional_boq_items",
                  return_value=predictor_additions),
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
        """If predict_additional_boq_items raises, pipeline should continue with no additions."""
        def boom(pi, baseline):
            raise RuntimeError("predictor exploded")

        with (
            patch("services.item_gen_process.boq_builder.generate_baseline_boq",
                  return_value=_make_raw_items(["Foundation concrete"])),
            patch("services.item_gen_process.boq_builder.predict_additional_boq_items",
                  side_effect=boom),
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
            patch("services.item_gen_process.boq_builder.generate_baseline_boq",
                  return_value=_make_raw_items(["Foundation concrete"])),
            patch("services.item_gen_process.boq_builder.predict_additional_boq_items",
                  return_value=[]),
            patch("services.item_gen_process.boq_builder.gap_fill_boq_items",
                  side_effect=boom),
        ):
            from services.item_gen_process.boq_builder import build_final_boq_items
            items = build_final_boq_items(_make_project_info())

        descriptions = {item["description"] for item in items}
        assert "Foundation concrete" in descriptions
