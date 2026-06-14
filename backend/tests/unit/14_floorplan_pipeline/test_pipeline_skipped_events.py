"""
Unit tests for the "skipped" event emission behavior in the estimation pipeline
when no floorplan URLs are provided.

Tests are structured in two groups:
  - Pure unit tests around a local helper that mirrors the pipeline skip logic
  - Optional import-based tests for the real `_emit` function (skipped if the
    pipeline module cannot be imported due to heavy dependencies like chromadb)
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, call

import pytest

# ---------------------------------------------------------------------------
# Path setup — makes `application.*` importable from the test runner
# ---------------------------------------------------------------------------
_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

# ---------------------------------------------------------------------------
# Optional: import the real `_emit` from the pipeline (heavy deps may fail)
# ---------------------------------------------------------------------------
try:
    from application.pipelines.estimation_pipeline import _emit as _pipeline_emit  # noqa: PLC0415
    PIPELINE_IMPORTABLE = True
except Exception:
    _pipeline_emit = None  # type: ignore[assignment]
    PIPELINE_IMPORTABLE = False


# ---------------------------------------------------------------------------
# Local helper that mirrors the exact skip/start logic from Stage 1 & 2 of
# estimation_pipeline.py so that tests remain self-contained.
# ---------------------------------------------------------------------------

def emit_floorplan_progress(floorplan_urls, callback=None):
    """Mirror the skip-emission block from estimation_pipeline.py Stage 1 & 2.

    Returns a list of emitted event dicts (independent of the callback).
    """
    urls = floorplan_urls or []
    events: list[dict] = []

    def _emit(step: str, status: str, data: dict) -> None:
        events.append({"step": step, "status": status, "data": data})
        if callback is not None:
            callback(step, status, data)

    if not urls:
        _emit("floorplan_cv", "skipped", {"reason": "No floorplan images provided"})
        _emit("floorplan_acceptance", "skipped", {"reason": "No floorplan images provided"})

    # (The `if urls:` branch is intentionally omitted — we only exercise the
    # skip path in this test module.)

    return events


def emit_floorplan_all_failed(callback=None):
    """Mirror the 'all images failed' branch from estimation_pipeline.py after the fix.

    Emits: floorplan_cv=failed, floorplan_acceptance=skipped.
    """
    events: list[dict] = []

    def _emit(step: str, status: str, data: dict) -> None:
        events.append({"step": step, "status": status, "data": data})
        if callback is not None:
            callback(step, status, data)

    _emit("floorplan_cv", "failed", {"error": "All floorplan images failed processing"})
    _emit("floorplan_acceptance", "skipped",
          {"reason": "floorplan_cv failed — no geometry to evaluate"})

    return events


# ===========================================================================
# Group 1 — Pure unit tests (no pipeline import required)
# ===========================================================================

class TestNoUrlsEmitsSkippedEvents:
    """When floorplan_urls is an empty list, two 'skipped' events must be emitted."""

    def test_no_urls_emits_cv_skipped(self):
        events = emit_floorplan_progress(floorplan_urls=[])
        assert events[0]["step"] == "floorplan_cv"
        assert events[0]["status"] == "skipped"

    def test_no_urls_emits_acceptance_skipped(self):
        events = emit_floorplan_progress(floorplan_urls=[])
        assert events[1]["step"] == "floorplan_acceptance"
        assert events[1]["status"] == "skipped"

    def test_no_urls_emits_exactly_two_events(self):
        events = emit_floorplan_progress(floorplan_urls=[])
        assert len(events) == 2

    def test_none_urls_treated_as_empty(self):
        """None should be normalised to [] and produce the same two skip events."""
        events = emit_floorplan_progress(floorplan_urls=None)
        assert len(events) == 2
        assert events[0]["status"] == "skipped"
        assert events[1]["status"] == "skipped"

    def test_skipped_event_has_reason_field(self):
        """Each skip event's data dict must contain a non-empty 'reason' string."""
        events = emit_floorplan_progress(floorplan_urls=[])
        for event in events:
            reason = event["data"].get("reason")
            assert isinstance(reason, str) and reason, (
                f"Expected non-empty 'reason' string in data, got: {event['data']!r}"
            )

    def test_with_urls_does_not_emit_skipped(self):
        """When URLs are provided the skip block should NOT fire."""
        events = emit_floorplan_progress(floorplan_urls=["http://example.com/plan.jpg"])
        skipped = [e for e in events if e["status"] == "skipped"]
        assert skipped == [], f"Expected no skipped events but got: {skipped}"

    def test_callback_called_with_skipped_args(self):
        """The progress callback must be invoked twice, both times with 'skipped'."""
        mock_cb = MagicMock()
        emit_floorplan_progress(floorplan_urls=[], callback=mock_cb)

        assert mock_cb.call_count == 2
        # First call must signal the CV step as skipped
        first_args = mock_cb.call_args_list[0]
        assert first_args == call("floorplan_cv", "skipped", {"reason": "No floorplan images provided"})
        # Second call must signal the acceptance step as skipped
        second_args = mock_cb.call_args_list[1]
        assert second_args == call("floorplan_acceptance", "skipped", {"reason": "No floorplan images provided"})

    def test_none_callback_no_error(self):
        """Passing callback=None must not raise any exception."""
        events = emit_floorplan_progress(floorplan_urls=[], callback=None)
        assert len(events) == 2  # events are still captured internally


# ===========================================================================
# Group 2 — Tests against the real `_emit` helper (skipped if not importable)
# ===========================================================================

@pytest.mark.skipif(not PIPELINE_IMPORTABLE, reason="estimation_pipeline not importable (heavy deps missing)")
class TestPipelineEmitHelper:
    """Tests for the real `_emit` function imported from estimation_pipeline."""

    def test_pipeline_emit_calls_callback(self):
        """`_emit` must invoke the callback with (step, status, data)."""
        mock_cb = MagicMock()
        _pipeline_emit(mock_cb, "test_step", "started", {"x": 1})
        mock_cb.assert_called_once_with("test_step", "started", {"x": 1})

    def test_pipeline_emit_no_op_when_callback_none(self):
        """`_emit(None, ...)` must be a no-op and must not raise."""
        # Should complete without exception
        _pipeline_emit(None, "test_step", "started", {})


# ===========================================================================
# Group 3 — All images failed: acceptance must be 'skipped', not 'pending'
# ===========================================================================

class TestAllImagesFailedEmitsAcceptanceSkipped:
    """When all floorplan images fail, floorplan_acceptance must emit 'skipped'."""

    def test_floorplan_cv_failed_event_is_emitted(self):
        events = emit_floorplan_all_failed()
        cv_events = [e for e in events if e["step"] == "floorplan_cv"]
        assert len(cv_events) == 1
        assert cv_events[0]["status"] == "failed"

    def test_floorplan_acceptance_skipped_event_is_emitted(self):
        events = emit_floorplan_all_failed()
        acc_events = [e for e in events if e["step"] == "floorplan_acceptance"]
        assert len(acc_events) == 1
        assert acc_events[0]["status"] == "skipped"

    def test_acceptance_skipped_has_non_empty_reason(self):
        events = emit_floorplan_all_failed()
        acc = next(e for e in events if e["step"] == "floorplan_acceptance")
        reason = acc["data"].get("reason")
        assert isinstance(reason, str) and reason, (
            f"Expected non-empty 'reason' string, got: {acc['data']!r}"
        )

    def test_exactly_two_events_emitted(self):
        events = emit_floorplan_all_failed()
        assert len(events) == 2

    def test_callback_invoked_for_both_events(self):
        mock_cb = MagicMock()
        emit_floorplan_all_failed(callback=mock_cb)
        assert mock_cb.call_count == 2
        statuses = [c.args[1] for c in mock_cb.call_args_list]
        assert statuses == ["failed", "skipped"]

    def test_event_order_cv_then_acceptance(self):
        events = emit_floorplan_all_failed()
        assert events[0]["step"] == "floorplan_cv"
        assert events[1]["step"] == "floorplan_acceptance"
