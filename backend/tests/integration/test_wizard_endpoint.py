"""Integration tests for the wizard form endpoints.

Covers:
- POST /api/estimate-project/form/validate — field-level validation
- POST /api/estimate-project/form/submit  — auth gating, pipeline kickoff
- GET  /api/estimate-project/form/stream/{session_id} — SSE session lookup

External dependencies (DB, Redis, LLM, pipeline) are fully mocked so these
tests run offline in any CI environment.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

pytestmark = pytest.mark.integration

# ── Payload helpers ────────────────────────────────────────────────────────────

def _residential_payload(**overrides) -> dict:
    base = {
        "building_type": "residential",
        "floor_count": 2,
        "floor_areas": [
            {"floor_label": "Ground Floor", "area_value": 120.0, "area_unit": "sqft"},
            {"floor_label": "First Floor", "area_value": 110.0, "area_unit": "sqft"},
        ],
        "bedrooms": 3,
        "bathrooms": 2,
        "finish_level": "standard",
        "structural_system": "framed",
        "roof_type": "clay_tile",
        "ceiling_type": "plastered",
    }
    base.update(overrides)
    return base


# ── /validate ─────────────────────────────────────────────────────────────────

class TestValidateEndpoint:
    async def test_valid_residential_payload_returns_valid_true(self, async_client):
        resp = await async_client.post(
            "/api/estimate-project/form/validate",
            json={"payload": _residential_payload()},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is True
        assert body["errors"] == {}

    async def test_missing_required_construction_details_returns_errors(self, async_client):
        # Remove required construction detail fields to trigger validation errors
        payload = _residential_payload()
        payload.pop("finish_level", None)
        payload.pop("structural_system", None)
        resp = await async_client.post(
            "/api/estimate-project/form/validate",
            json={"payload": payload},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is False
        assert len(body["errors"]) > 0

    async def test_pydantic_schema_violation_returns_422(self, async_client):
        # floor_count=0 violates ge=1 constraint in WizardFormPayload
        payload = _residential_payload(floor_count=0)
        resp = await async_client.post(
            "/api/estimate-project/form/validate",
            json={"payload": payload},
        )
        assert resp.status_code == 422

    async def test_commercial_payload_without_primary_use_type_returns_errors(self, async_client):
        payload = {
            "building_type": "commercial",
            "floor_count": 1,
            "floor_areas": [{"floor_label": "G", "area_value": 200.0, "area_unit": "sqft"}],
            "washroom_count": 2,
            "finish_level": "standard",
            "structural_system": "framed",
            "roof_type": "flat_slab",
            "ceiling_type": "suspended",
            # primary_use_type intentionally omitted
        }
        resp = await async_client.post(
            "/api/estimate-project/form/validate",
            json={"payload": payload},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is False


# ── /submit ───────────────────────────────────────────────────────────────────

class TestSubmitEndpoint:
    async def test_missing_auth_returns_401(self, unauthed_client):
        resp = await unauthed_client.post(
            "/api/estimate-project/form/submit",
            json=_residential_payload(),
        )
        assert resp.status_code == 401

    async def test_invalid_payload_returns_422(self, async_client):
        # floor_areas is required — omitting it triggers Pydantic 422
        resp = await async_client.post(
            "/api/estimate-project/form/submit",
            json={"building_type": "residential", "floor_count": 1},
        )
        assert resp.status_code == 422

    async def test_valid_payload_kicks_off_pipeline_and_returns_session(
        self, async_client, monkeypatch
    ):
        fake_session = MagicMock()
        fake_session.session_id = "sess-abc-123"

        monkeypatch.setattr(
            "app.api.controllers.form_controller.process_store.create_session",
            AsyncMock(return_value=fake_session),
        )

        fake_estimate_id = str(uuid.uuid4())

        def _mock_refresh(obj):
            obj.id = uuid.UUID(fake_estimate_id)

        async_client.mock_db.refresh.side_effect = _mock_refresh

        with (
            patch(
                "app.api.controllers.form_controller.FormService.run_pipeline_and_complete",
                new_callable=AsyncMock,
            ),
            patch("app.api.controllers.form_controller.asyncio.create_task"),
            patch("app.api.controllers.form_controller.run_registry.register"),
        ):
            resp = await async_client.post(
                "/api/estimate-project/form/submit",
                json=_residential_payload(),
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["session_id"] == "sess-abc-123"
        assert body["status"] == "processing"
        assert "estimate_id" in body

    async def test_business_validation_failure_returns_422(self, async_client, monkeypatch):
        # Simulate a payload that passes Pydantic but fails business validation
        monkeypatch.setattr(
            "app.api.controllers.form_controller.validate_wizard_payload",
            lambda raw: {"bedrooms": "required for residential"},
        )
        resp = await async_client.post(
            "/api/estimate-project/form/submit",
            json=_residential_payload(),
        )
        assert resp.status_code == 422


# ── /stream/{session_id} ──────────────────────────────────────────────────────

class TestStreamEndpoint:
    async def test_unknown_session_returns_404(self, async_client, monkeypatch):
        monkeypatch.setattr(
            "app.api.controllers.form_controller.process_store.get_session",
            AsyncMock(return_value=None),
        )
        resp = await async_client.get("/api/estimate-project/form/stream/nonexistent-id")
        assert resp.status_code == 404
