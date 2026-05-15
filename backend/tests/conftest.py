"""Shared pytest fixtures for backend tests.

Environment variables are set at module load time (before any backend import
that touches settings), so all test files in this directory get them for free.
"""
import os
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# ── Path & env setup (must precede backend imports) ───────────────────────────
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("POSTGRES_DB", "testdb")
os.environ.setdefault("EMBEDDING_MODEL", "test-model")
os.environ.setdefault("RETRIEVAL_TOP_K", "5")
os.environ.setdefault("MIN_CONFIDENCE_THRESHOLD", "0.5")
os.environ.setdefault("ENV", "development")

import jwt  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import AsyncClient, ASGITransport  # noqa: E402

from app.api.server import app  # noqa: E402
from app.api.middleware.auth_dependency import get_current_user_id  # noqa: E402
from app.api.state.session import process_store  # noqa: E402
from core.config.settings import settings  # noqa: E402
from infrastructure.data_layer.database.session import get_db_session  # noqa: E402

# ── Test constants ─────────────────────────────────────────────────────────────
TEST_USER_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
TEST_ESTIMATE_ID = "11111111-2222-3333-4444-555555555555"


def make_jwt(user_id: str = TEST_USER_ID) -> str:
    payload = {"sub": user_id, "exp": int(time.time()) + 3600}
    return jwt.encode(payload, settings.api_secret_key, algorithm="HS256")


# ── Shared fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {make_jwt()}"}


@pytest_asyncio.fixture
async def async_client(monkeypatch) -> AsyncClient:
    """ASGI test client with mocked startup events and dependency overrides.

    - Startup side-effects (DB migrations, Redis, cleanup task) are suppressed.
    - get_current_user_id → TEST_USER_ID
    - get_db_session → MagicMock; access via client.mock_db to configure return values.
    """
    mock_db = MagicMock()

    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_db_session] = lambda: mock_db

    monkeypatch.setattr(process_store, "start_cleanup", lambda: None)

    with (
        patch("services.rag_process.service.init_db"),
        patch("app.api.server.init_redis", new_callable=AsyncMock),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            client.mock_db = mock_db  # type: ignore[attr-defined]
            yield client

    app.dependency_overrides.pop(get_current_user_id, None)
    app.dependency_overrides.pop(get_db_session, None)


@pytest_asyncio.fixture
async def unauthed_client(monkeypatch) -> AsyncClient:
    """ASGI test client WITHOUT authentication override.

    Use this to verify that protected endpoints return 401 when no valid token
    is provided. The DB session is still mocked to avoid real DB connections.
    """
    mock_db = MagicMock()
    app.dependency_overrides[get_db_session] = lambda: mock_db

    monkeypatch.setattr(process_store, "start_cleanup", lambda: None)

    with (
        patch("services.rag_process.service.init_db"),
        patch("app.api.server.init_redis", new_callable=AsyncMock),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client

    app.dependency_overrides.pop(get_db_session, None)
