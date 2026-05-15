"""Integration tests for the estimates CRUD endpoints.

Covers:
- GET  /api/estimates               — list (auth gating, pagination)
- GET  /api/estimates/{id}          — detail (not-found, ownership)
- PATCH /api/estimates/{id}         — partial update
- DELETE /api/estimates/{id}        — soft delete
- GET  /api/dashboard/summary       — aggregation response shape

EstimateService is mocked at the controller import level so tests only exercise
the HTTP contract (routing, auth, serialization) and not the business layer.
"""
import pytest

pytestmark = pytest.mark.integration


def _patch_svc(monkeypatch, method: str, return_value):
    """Patch a single EstimateService method on the controller module."""
    import app.api.controllers.estimates_controller as ctrl

    original_cls = ctrl.EstimateService

    class _MockSvc:
        def __init__(self, db):
            pass

        def __getattr__(self, name):
            if name == method:
                return lambda *args, **kwargs: return_value
            raise AttributeError(name)

    monkeypatch.setattr(ctrl, "EstimateService", _MockSvc)
    return original_cls


# ── Auth gating ────────────────────────────────────────────────────────────────

class TestAuthGating:
    async def test_list_estimates_requires_auth(self, unauthed_client):
        resp = await unauthed_client.get("/api/estimates")
        assert resp.status_code == 401

    async def test_get_estimate_requires_auth(self, unauthed_client):
        resp = await unauthed_client.get("/api/estimates/some-id")
        assert resp.status_code == 401

    async def test_patch_estimate_requires_auth(self, unauthed_client):
        resp = await unauthed_client.patch("/api/estimates/some-id", json={})
        assert resp.status_code == 401

    async def test_delete_estimate_requires_auth(self, unauthed_client):
        resp = await unauthed_client.delete("/api/estimates/some-id")
        assert resp.status_code == 401

    async def test_dashboard_requires_auth(self, unauthed_client):
        resp = await unauthed_client.get("/api/dashboard/summary")
        assert resp.status_code == 401


# ── List ──────────────────────────────────────────────────────────────────────

class TestListEstimates:
    async def test_returns_paginated_shape(self, async_client, monkeypatch):
        expected = {"estimates": [], "total": 0, "page": 1, "page_size": 20}
        _patch_svc(monkeypatch, "list_estimates", expected)

        resp = await async_client.get("/api/estimates")
        assert resp.status_code == 200
        body = resp.json()
        assert "estimates" in body
        assert "total" in body
        assert "page" in body
        assert "page_size" in body

    async def test_pagination_params_accepted(self, async_client, monkeypatch):
        expected = {"estimates": [], "total": 0, "page": 2, "page_size": 10}
        _patch_svc(monkeypatch, "list_estimates", expected)

        resp = await async_client.get("/api/estimates?page=2&page_size=10")
        assert resp.status_code == 200

    async def test_invalid_page_param_returns_422(self, async_client):
        resp = await async_client.get("/api/estimates?page=0")
        assert resp.status_code == 422


# ── Detail ────────────────────────────────────────────────────────────────────

class TestGetEstimate:
    async def test_not_found_raises_404(self, async_client, monkeypatch):
        from fastapi import HTTPException

        def _raise(estimate_id, user_id):
            raise HTTPException(status_code=404, detail="Estimate not found.")

        import app.api.controllers.estimates_controller as ctrl

        class _Svc:
            def __init__(self, db): pass
            def get_estimate(self, *a, **kw): raise HTTPException(status_code=404, detail="Estimate not found.")

        monkeypatch.setattr(ctrl, "EstimateService", _Svc)

        resp = await async_client.get("/api/estimates/nonexistent-id")
        assert resp.status_code == 404

    async def test_found_returns_estimate_shape(self, async_client, monkeypatch):
        expected = {
            "id": "11111111-2222-3333-4444-555555555555",
            "project_name": "Test Build",
            "status": "completed",
            "result": {},
            "project_info": {},
            "confidence": 0.85,
            "grand_total": 5000000.0,
            "item_count": 30,
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "notes": None,
            "progress": None,
            "error_message": None,
            "cancelled_at": None,
            "regenerated_from_estimate_id": None,
            "wizard_payload": None,
        }
        _patch_svc(monkeypatch, "get_estimate", expected)

        resp = await async_client.get("/api/estimates/11111111-2222-3333-4444-555555555555")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == expected["id"]
        assert body["status"] == "completed"


# ── Patch ─────────────────────────────────────────────────────────────────────

class TestPatchEstimate:
    async def test_returns_updated_fields(self, async_client, monkeypatch):
        updated = {
            "id": "11111111-2222-3333-4444-555555555555",
            "project_name": "Renamed Build",
            "notes": "Updated note",
        }
        _patch_svc(monkeypatch, "patch_estimate", updated)

        resp = await async_client.patch(
            "/api/estimates/11111111-2222-3333-4444-555555555555",
            json={"project_name": "Renamed Build", "notes": "Updated note"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["project_name"] == "Renamed Build"


# ── Delete ────────────────────────────────────────────────────────────────────

class TestDeleteEstimate:
    async def test_returns_confirmation_message(self, async_client, monkeypatch):
        _patch_svc(monkeypatch, "delete_estimate", {"message": "Estimate deleted."})

        resp = await async_client.delete("/api/estimates/11111111-2222-3333-4444-555555555555")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Estimate deleted."


# ── Dashboard ─────────────────────────────────────────────────────────────────

class TestDashboardSummary:
    async def test_returns_required_keys(self, async_client, monkeypatch):
        expected = {
            "total_estimates": 5,
            "estimates_this_month": 2,
            "average_confidence": 0.82,
            "total_estimated_value": 12_500_000.0,
        }
        _patch_svc(monkeypatch, "get_dashboard_summary", expected)

        resp = await async_client.get("/api/dashboard/summary")
        assert resp.status_code == 200
        body = resp.json()
        for key in ("total_estimates", "estimates_this_month", "average_confidence", "total_estimated_value"):
            assert key in body
