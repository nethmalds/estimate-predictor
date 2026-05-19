"""Unit tests for build_report in report_builder.py.

Covers:
- BE-TC-093: output contains required top-level keys (summary, details)
- BE-TC-094: summary.rate_review_items lists only items needing review
- BE-TC-095: summary.boq_source_breakdown counts items per source
- BE-TC-096: floorplan_audit reflects accepted: false when floorplan rejected
"""
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from services.reporting_process.report_builder import build_report  # noqa: E402


def _base_payload(**overrides) -> dict:
    payload = {
        "project_info": {
            "building_type": "residential",
            "floors": 2,
            "applied_defaults": [],
            "preprocessing_warnings": [],
            "parameters": {
                "bedrooms": 3,
                "bathrooms": 2,
                "built_up_area": 250.0,
                "finish_level": "standard",
                "roof_type": "clay_tile",
            },
        },
        "boq_items": [],
        "costs": {
            "total": 5_000_000.0,
            "base_total": 4_000_000.0,
            "external_works_total": 0.0,
            "preliminaries": 320_000.0,
            "preliminaries_rate": 0.08,
            "contingencies": 200_000.0,
            "contingencies_rate": 0.05,
        },
        "confidence": {"score": 0.82},
        "floorplan": {"available": False, "accepted": None},
        "sources": {"boq_method": "llm"},
    }
    payload.update(overrides)
    return payload


# ── BE-TC-093: required top-level keys ────────────────────────────────────────

class TestRequiredTopLevelKeys:
    def test_output_has_summary_key(self):
        result = build_report(_base_payload())
        assert "summary" in result

    def test_output_has_details_key(self):
        result = build_report(_base_payload())
        assert "details" in result

    def test_summary_has_total(self):
        result = build_report(_base_payload())
        assert result["summary"]["total"] == 5_000_000.0

    def test_summary_has_confidence(self):
        result = build_report(_base_payload())
        assert result["summary"]["confidence"] == 0.82

    def test_summary_has_floorplan_audit(self):
        result = build_report(_base_payload())
        assert "floorplan_audit" in result["summary"]

    def test_summary_has_boq_source_breakdown(self):
        result = build_report(_base_payload())
        assert "boq_source_breakdown" in result["summary"]

    def test_summary_has_rate_review_items(self):
        result = build_report(_base_payload())
        assert "rate_review_items" in result["summary"]

    def test_details_is_the_full_payload(self):
        payload = _base_payload()
        result = build_report(payload)
        assert result["details"] is payload


# ── BE-TC-094: rate_review_items lists only flagged items ─────────────────────

class TestRateReviewItems:
    def test_item_with_needs_rate_review_true_included(self):
        items = [
            {"description": "Flagged item", "category": "brick_masonry",
             "match_type": "soft_match", "bsr_item_no": "A1.1",
             "needs_rate_review": True},
            {"description": "Good item", "category": "concrete_works",
             "match_type": "confirmed", "bsr_item_no": "B2.1",
             "needs_rate_review": False},
        ]
        result = build_report(_base_payload(boq_items=items))
        review = result["summary"]["rate_review_items"]
        descriptions = [r["description"] for r in review]
        assert "Flagged item" in descriptions
        assert "Good item" not in descriptions

    def test_item_with_match_type_no_match_included(self):
        items = [
            {"description": "Unmatched item", "category": "plastering_and_rendering",
             "match_type": "no_match", "bsr_item_no": None,
             "needs_rate_review": False},
        ]
        result = build_report(_base_payload(boq_items=items))
        review = result["summary"]["rate_review_items"]
        assert any(r["description"] == "Unmatched item" for r in review)

    def test_no_flagged_items_yields_empty_list(self):
        items = [
            {"description": "Good item", "category": "concrete_works",
             "match_type": "confirmed", "bsr_item_no": "B2.1",
             "needs_rate_review": False},
        ]
        result = build_report(_base_payload(boq_items=items))
        assert result["summary"]["rate_review_items"] == []

    def test_empty_boq_yields_empty_review_list(self):
        result = build_report(_base_payload(boq_items=[]))
        assert result["summary"]["rate_review_items"] == []


# ── BE-TC-095: boq_source_breakdown counts per source ────────────────────────

class TestBOQSourceBreakdown:
    def test_counts_items_by_source(self):
        items = [
            {"description": "A", "source": "llm", "match_type": "confirmed", "needs_rate_review": False},
            {"description": "B", "source": "llm", "match_type": "confirmed", "needs_rate_review": False},
            {"description": "C", "source": "rule_based", "match_type": "confirmed", "needs_rate_review": False},
        ]
        result = build_report(_base_payload(boq_items=items))
        breakdown = result["summary"]["boq_source_breakdown"]
        assert breakdown.get("llm") == 2
        assert breakdown.get("rule_based") == 1

    def test_items_without_source_counted_as_unknown(self):
        items = [
            {"description": "X", "match_type": "confirmed", "needs_rate_review": False},
        ]
        result = build_report(_base_payload(boq_items=items))
        breakdown = result["summary"]["boq_source_breakdown"]
        assert breakdown.get("unknown") == 1

    def test_empty_boq_yields_empty_breakdown(self):
        result = build_report(_base_payload(boq_items=[]))
        assert result["summary"]["boq_source_breakdown"] == {}


# ── BE-TC-096: floorplan_audit reflects rejected state ───────────────────────

class TestFloorplanAudit:
    def test_rejected_floorplan_audit_has_accepted_false(self):
        payload = _base_payload(floorplan={
            "available": False,
            "accepted": False,
            "rejection_reason": "low confidence",
            "geometry_confidence": 0.10,
        })
        result = build_report(payload)
        audit = result["summary"]["floorplan_audit"]
        assert audit["accepted"] is False

    def test_rejected_floorplan_audit_has_rejection_reason(self):
        payload = _base_payload(floorplan={
            "available": False,
            "accepted": False,
            "rejection_reason": "low confidence",
            "geometry_confidence": 0.10,
        })
        result = build_report(payload)
        audit = result["summary"]["floorplan_audit"]
        assert audit["rejection_reason"] == "low confidence"

    def test_accepted_floorplan_has_accepted_true(self):
        payload = _base_payload(floorplan={
            "available": True,
            "accepted": True,
            "geometry_confidence": 0.85,
            "total_floor_area_m2": 250.0,
            "room_count": 5,
        })
        result = build_report(payload)
        audit = result["summary"]["floorplan_audit"]
        assert audit["accepted"] is True

    def test_no_floorplan_audit_accepted_is_none(self):
        payload = _base_payload(floorplan={"available": False})
        result = build_report(payload)
        audit = result["summary"]["floorplan_audit"]
        assert audit["accepted"] is None
