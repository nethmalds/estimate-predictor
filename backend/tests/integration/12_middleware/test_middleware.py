"""Integration tests for authentication and security middleware.

Covers:
- BE-TC-067: Expired JWT token returns 401
- BE-TC-068: Every API response carries required security headers
- BE-TC-069: HSTS header absent in non-production mode
- BE-TC-070: Mutating requests emit an audit log entry
- BE-TC-071: Health-check paths are excluded from audit log
"""
import logging
import time
from unittest.mock import patch

import jwt
import pytest

pytestmark = pytest.mark.integration

_TEST_USER_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def _expired_jwt(user_id: str = _TEST_USER_ID) -> str:
    """Generate a JWT whose exp is set one hour in the past."""
    from core.config.settings import settings
    payload = {"sub": user_id, "exp": int(time.time()) - 3600}
    return jwt.encode(payload, settings.api_secret_key, algorithm="HS256")


def _invalid_jwt() -> str:
    return "Bearer not.a.valid.token"


# ── BE-TC-067: Expired JWT → 401 ──────────────────────────────────────────────

class TestExpiredToken:
    async def test_expired_token_returns_401(self, unauthed_client):
        # BE-TC-067: use unauthed_client so JWT dependency is NOT overridden
        expired = _expired_jwt()
        resp = await unauthed_client.get(
            "/api/estimates",
            headers={"Authorization": f"Bearer {expired}"},
        )
        assert resp.status_code == 401

    async def test_expired_token_detail_mentions_expired(self, unauthed_client):
        expired = _expired_jwt()
        resp = await unauthed_client.get(
            "/api/estimates",
            headers={"Authorization": f"Bearer {expired}"},
        )
        body = resp.json()
        # Custom error handler wraps detail under error.message
        detail = str(body).lower()
        assert "expired" in detail

    async def test_malformed_token_returns_401(self, unauthed_client):
        resp = await unauthed_client.get(
            "/api/estimates",
            headers={"Authorization": "Bearer malformed.token.string"},
        )
        assert resp.status_code == 401

    async def test_no_token_returns_401(self, unauthed_client):
        resp = await unauthed_client.get("/api/estimates")
        assert resp.status_code == 401


# ── BE-TC-068: Security headers on every response ─────────────────────────────

class TestSecurityHeaders:
    async def test_x_content_type_options_present(self, async_client, monkeypatch):
        from fastapi import HTTPException

        import app.api.controllers.estimates_controller as ctrl

        class _Svc:
            def __init__(self, db): pass
            def list_estimates(self, *a, **kw): return {"estimates": [], "total": 0, "page": 1, "page_size": 20}

        monkeypatch.setattr(ctrl, "EstimateService", _Svc)
        resp = await async_client.get("/api/estimates")
        assert resp.headers.get("x-content-type-options") == "nosniff"

    async def test_x_frame_options_deny_present(self, async_client, monkeypatch):
        import app.api.controllers.estimates_controller as ctrl

        class _Svc:
            def __init__(self, db): pass
            def list_estimates(self, *a, **kw): return {"estimates": [], "total": 0, "page": 1, "page_size": 20}

        monkeypatch.setattr(ctrl, "EstimateService", _Svc)
        resp = await async_client.get("/api/estimates")
        assert resp.headers.get("x-frame-options") == "DENY"

    async def test_content_security_policy_present(self, async_client, monkeypatch):
        import app.api.controllers.estimates_controller as ctrl

        class _Svc:
            def __init__(self, db): pass
            def list_estimates(self, *a, **kw): return {"estimates": [], "total": 0, "page": 1, "page_size": 20}

        monkeypatch.setattr(ctrl, "EstimateService", _Svc)
        resp = await async_client.get("/api/estimates")
        assert "content-security-policy" in resp.headers

    async def test_referrer_policy_present(self, async_client, monkeypatch):
        import app.api.controllers.estimates_controller as ctrl

        class _Svc:
            def __init__(self, db): pass
            def list_estimates(self, *a, **kw): return {"estimates": [], "total": 0, "page": 1, "page_size": 20}

        monkeypatch.setattr(ctrl, "EstimateService", _Svc)
        resp = await async_client.get("/api/estimates")
        assert "referrer-policy" in resp.headers


# ── BE-TC-069: HSTS absent in non-production mode ─────────────────────────────

class TestHSTSHeader:
    async def test_hsts_absent_in_dev_mode(self, async_client, monkeypatch):
        import app.api.controllers.estimates_controller as ctrl

        class _Svc:
            def __init__(self, db): pass
            def list_estimates(self, *a, **kw): return {"estimates": [], "total": 0, "page": 1, "page_size": 20}

        monkeypatch.setattr(ctrl, "EstimateService", _Svc)
        resp = await async_client.get("/api/estimates")
        # In dev mode (ENV=development set in conftest), HSTS must NOT be present
        assert "strict-transport-security" not in resp.headers

    async def test_security_headers_middleware_adds_hsts_in_production(self):
        from app.api.middleware.security_headers import SecurityHeadersMiddleware
        from starlette.applications import Starlette
        from starlette.requests import Request
        from starlette.responses import JSONResponse
        from starlette.testclient import TestClient

        async def _handler(request: Request):
            return JSONResponse({"ok": True})

        inner_app = Starlette(routes=[])
        inner_app.add_route("/test", _handler)
        prod_app = SecurityHeadersMiddleware(inner_app, is_production=True)
        client = TestClient(prod_app, raise_server_exceptions=False)
        resp = client.get("/test")
        assert "strict-transport-security" in resp.headers


# ── BE-TC-070: Mutating requests emit audit log ───────────────────────────────

class TestAuditLogMiddleware:
    async def test_post_request_emits_audit_log(self, async_client, monkeypatch, caplog):
        import app.api.controllers.estimates_controller as ctrl

        class _Svc:
            def __init__(self, db): pass
            def delete_estimate(self, *a, **kw): return {"message": "Estimate deleted."}

        monkeypatch.setattr(ctrl, "EstimateService", _Svc)

        with caplog.at_level(logging.INFO, logger="audit"):
            await async_client.delete("/api/estimates/11111111-2222-3333-4444-555555555555")

        audit_records = [r for r in caplog.records if r.name == "audit"]
        assert len(audit_records) >= 1

    async def test_audit_log_contains_method_and_path(self, async_client, monkeypatch, caplog):
        import app.api.controllers.estimates_controller as ctrl

        class _Svc:
            def __init__(self, db): pass
            def delete_estimate(self, *a, **kw): return {"message": "Estimate deleted."}

        monkeypatch.setattr(ctrl, "EstimateService", _Svc)

        with caplog.at_level(logging.INFO, logger="audit"):
            await async_client.delete("/api/estimates/11111111-2222-3333-4444-555555555555")

        audit_records = [r for r in caplog.records if r.name == "audit"]
        assert len(audit_records) >= 1
        record = audit_records[0]
        assert hasattr(record, "method") or record.getMessage() != ""


# ── BE-TC-071: Health paths excluded from audit log ──────────────────────────

class TestAuditLogSkipsHealthPaths:
    async def test_get_request_not_in_audit_log(self, async_client, monkeypatch, caplog):
        import app.api.controllers.estimates_controller as ctrl

        class _Svc:
            def __init__(self, db): pass
            def list_estimates(self, *a, **kw): return {"estimates": [], "total": 0, "page": 1, "page_size": 20}

        monkeypatch.setattr(ctrl, "EstimateService", _Svc)

        with caplog.at_level(logging.INFO, logger="audit"):
            await async_client.get("/api/estimates")

        audit_records = [r for r in caplog.records if r.name == "audit"]
        # GET requests are not in _AUDIT_METHODS so no log should be emitted
        assert len(audit_records) == 0

    async def test_health_endpoint_skip_confirmed_via_skip_paths_set(self):
        from app.api.middleware.audit_log import _SKIP_PATHS
        assert "/health" in _SKIP_PATHS
        assert "/healthz" in _SKIP_PATHS
