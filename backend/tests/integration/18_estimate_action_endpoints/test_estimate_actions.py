"""Integration tests for estimate action endpoints.

Covers:
- BE-TC-097: Authenticated user can duplicate an existing estimate
- BE-TC-098: Duplicating a non-existent estimate returns 404
- BE-TC-099: Authenticated user can cancel an in-progress estimate
- BE-TC-100: Regenerate creates a new child estimate from source
- BE-TC-101: Floorplan OCR endpoint extracts geometry from a valid image path

EstimateService and run_pipeline are patched at the controller level.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException

pytestmark = pytest.mark.integration


def _patch_svc(monkeypatch, method: str, return_value=None, exc: Exception | None = None):
    """Patch a single EstimateService method on the estimates_controller module."""
    import app.api.controllers.estimates_controller as ctrl

    class _MockSvc:
        def __init__(self, db):
            pass

        def __getattr__(self, name):
            if name == method:
                if exc is not None:
                    async def _raise(*a, **kw):
                        raise exc
                    def _raise_sync(*a, **kw):
                        raise exc
                    # Return whichever suits the caller
                    return _raise_sync
                return lambda *args, **kwargs: return_value
            raise AttributeError(name)

    monkeypatch.setattr(ctrl, "EstimateService", _MockSvc)


def _patch_svc_async(monkeypatch, method: str, return_value=None, exc: Exception | None = None):
    """Patch an async EstimateService method."""
    import app.api.controllers.estimates_controller as ctrl
    from unittest.mock import AsyncMock

    class _MockSvc:
        def __init__(self, db):
            pass

        def __getattr__(self, name):
            if name == method:
                if exc is not None:
                    async def _raise(*a, **kw):
                        raise exc
                    return _raise
                mock = AsyncMock(return_value=return_value)
                return mock
            raise AttributeError(name)

    monkeypatch.setattr(ctrl, "EstimateService", _MockSvc)


# ── BE-TC-097: Duplicate estimate ─────────────────────────────────────────────

class TestDuplicateEstimate:
    async def test_duplicate_returns_200_with_new_estimate(self, async_client, monkeypatch):
        _patch_svc(monkeypatch, "duplicate_estimate", {
            "id": "99999999-aaaa-bbbb-cccc-dddddddddddd",
            "project_name": "Copy of Test Build",
            "status": "pending",
        })
        resp = await async_client.post(
            "/api/estimates/11111111-2222-3333-4444-555555555555/duplicate"
        )
        assert resp.status_code == 200

    async def test_duplicate_response_has_different_id(self, async_client, monkeypatch):
        original_id = "11111111-2222-3333-4444-555555555555"
        new_id = "99999999-aaaa-bbbb-cccc-dddddddddddd"
        _patch_svc(monkeypatch, "duplicate_estimate", {
            "id": new_id,
            "project_name": "Copy",
            "status": "pending",
        })
        resp = await async_client.post(f"/api/estimates/{original_id}/duplicate")
        body = resp.json()
        assert body["id"] == new_id
        assert body["id"] != original_id

    # ── BE-TC-098: Duplicate non-existent → 404 ──────────────────────────────

    async def test_duplicate_nonexistent_returns_404(self, async_client, monkeypatch):
        null_uuid = "00000000-0000-0000-0000-000000000000"
        _patch_svc(monkeypatch, "duplicate_estimate",
                   exc=HTTPException(status_code=404, detail="Estimate not found."))
        resp = await async_client.post(f"/api/estimates/{null_uuid}/duplicate")
        assert resp.status_code == 404

    async def test_duplicate_requires_auth(self, unauthed_client):
        resp = await unauthed_client.post(
            "/api/estimates/11111111-2222-3333-4444-555555555555/duplicate"
        )
        assert resp.status_code == 401


# ── BE-TC-099: Cancel estimate ────────────────────────────────────────────────

class TestCancelEstimate:
    async def test_cancel_returns_200_with_cancelled_status(self, async_client, monkeypatch):
        _patch_svc(monkeypatch, "cancel_estimate", {
            "id": "11111111-2222-3333-4444-555555555555",
            "status": "cancelled",
            "cancelled_at": "2026-05-16T12:00:00+00:00",
        })
        resp = await async_client.post(
            "/api/estimates/11111111-2222-3333-4444-555555555555/cancel"
        )
        assert resp.status_code == 200

    async def test_cancel_response_has_cancelled_status(self, async_client, monkeypatch):
        _patch_svc(monkeypatch, "cancel_estimate", {
            "id": "11111111-2222-3333-4444-555555555555",
            "status": "cancelled",
            "cancelled_at": "2026-05-16T12:00:00+00:00",
        })
        resp = await async_client.post(
            "/api/estimates/11111111-2222-3333-4444-555555555555/cancel"
        )
        body = resp.json()
        assert body["status"] == "cancelled"
        assert body["cancelled_at"] is not None

    async def test_cancel_nonexistent_returns_404(self, async_client, monkeypatch):
        null_uuid = "00000000-0000-0000-0000-000000000000"
        _patch_svc(monkeypatch, "cancel_estimate",
                   exc=HTTPException(status_code=404, detail="Estimate not found."))
        resp = await async_client.post(f"/api/estimates/{null_uuid}/cancel")
        assert resp.status_code == 404

    async def test_cancel_requires_auth(self, unauthed_client):
        resp = await unauthed_client.post(
            "/api/estimates/11111111-2222-3333-4444-555555555555/cancel"
        )
        assert resp.status_code == 401


# ── BE-TC-100: Regenerate estimate ────────────────────────────────────────────

class TestRegenerateEstimate:
    async def test_regenerate_returns_200(self, async_client, monkeypatch):
        _patch_svc_async(monkeypatch, "regenerate_estimate", {
            "id": "88888888-aaaa-bbbb-cccc-dddddddddddd",
            "status": "processing",
            "regenerated_from_estimate_id": "11111111-2222-3333-4444-555555555555",
        })
        resp = await async_client.post(
            "/api/estimates/11111111-2222-3333-4444-555555555555/regenerate"
        )
        assert resp.status_code == 200

    async def test_regenerate_response_has_source_id(self, async_client, monkeypatch):
        source_id = "11111111-2222-3333-4444-555555555555"
        _patch_svc_async(monkeypatch, "regenerate_estimate", {
            "id": "88888888-aaaa-bbbb-cccc-dddddddddddd",
            "status": "processing",
            "regenerated_from_estimate_id": source_id,
        })
        resp = await async_client.post(f"/api/estimates/{source_id}/regenerate")
        body = resp.json()
        assert body["regenerated_from_estimate_id"] == source_id

    async def test_regenerate_requires_auth(self, unauthed_client):
        resp = await unauthed_client.post(
            "/api/estimates/11111111-2222-3333-4444-555555555555/regenerate"
        )
        assert resp.status_code == 401

    async def test_regenerate_nonexistent_returns_404(self, async_client, monkeypatch):
        null_uuid = "00000000-0000-0000-0000-000000000000"
        _patch_svc_async(monkeypatch, "regenerate_estimate",
                         exc=HTTPException(status_code=404, detail="Estimate not found."))
        resp = await async_client.post(f"/api/estimates/{null_uuid}/regenerate")
        assert resp.status_code == 404


# ── BE-TC-101: Floorplan OCR endpoint ────────────────────────────────────────

class TestFloorplanOCREndpoint:
    async def test_valid_image_path_returns_200_with_geometry(self, async_client, monkeypatch):
        mock_result = {
            "total_floor_area_m2": 185.5,
            "geometry_confidence": 0.82,
            "room_count": 5,
            "opening_count": 12,
        }
        monkeypatch.setattr(
            "app.api.controllers.project_controller.run_pipeline",
            lambda path: mock_result,
        )
        resp = await async_client.post(
            "/api/floorplan-ocr",
            json={"image_path": "/some/path/to/floorplan.png"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "total_floor_area_m2" in body
        assert "geometry_confidence" in body

    async def test_missing_image_path_returns_422(self, async_client):
        resp = await async_client.post("/api/floorplan-ocr", json={})
        assert resp.status_code == 422

    async def test_pipeline_file_not_found_returns_404(self, async_client, monkeypatch):
        def _raise(path):
            raise FileNotFoundError("Image not found.")

        monkeypatch.setattr(
            "app.api.controllers.project_controller.run_pipeline",
            _raise,
        )
        resp = await async_client.post(
            "/api/floorplan-ocr",
            json={"image_path": "/nonexistent/path.png"},
        )
        assert resp.status_code == 404

    async def test_pipeline_value_error_returns_400(self, async_client, monkeypatch):
        def _raise(path):
            raise ValueError("Cannot process image format.")

        monkeypatch.setattr(
            "app.api.controllers.project_controller.run_pipeline",
            _raise,
        )
        resp = await async_client.post(
            "/api/floorplan-ocr",
            json={"image_path": "/bad/format.bmp"},
        )
        assert resp.status_code == 400
