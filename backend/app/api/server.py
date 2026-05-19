
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.middleware.audit_log import AuditLogMiddleware
from app.api.middleware.rate_limit import limiter
from app.api.middleware.request_id import RequestIDMiddleware
from app.api.middleware.security_headers import SecurityHeadersMiddleware
from app.api.routes.router import router as api_router
from app.api.state.session import process_store
from core.config.settings import settings
from core.exceptions.error_handlers import register_exception_handlers
from core.logging import configure_logging
from infrastructure.cache.redis_client import init_redis, close_redis

# Initialise structured logging before anything else emits records
configure_logging(level="DEBUG" if settings.env == "development" else "INFO")

logger = logging.getLogger(__name__)

_IS_PRODUCTION = settings.env.lower() == "production"

# In production, restrict methods and headers to only what the API uses.
# In development, keep open to ease local tooling (Postman, curl, etc.).
_CORS_METHODS = (
    ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    if _IS_PRODUCTION
    else ["*"]
)
_CORS_HEADERS = (
    ["Authorization", "Content-Type", "X-Request-ID", "Accept"]
    if _IS_PRODUCTION
    else ["*"]
)

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
# Middleware stack — outermost first (added last in Starlette's reversed order):
# RequestID → AuditLog → SecurityHeaders → CORS
app.add_middleware(SecurityHeadersMiddleware, is_production=_IS_PRODUCTION)
app.add_middleware(AuditLogMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=_CORS_METHODS,
    allow_headers=_CORS_HEADERS,
)
register_exception_handlers(app)
app.include_router(api_router)


@app.on_event("startup")
async def startup_event() -> None:
    from services.rag_process.service import init_db
    # Run Alembic migrations synchronously (fast, ~1-2s)
    init_db()
    # Connect to Redis (no-op + warning if REDIS_URL unset)
    await init_redis()
    # Start session cleanup loop
    process_store.start_cleanup()
    # Pre-load YOLO model in the main thread so the CPU context is ready before
    # the first asyncio.to_thread pipeline call attempts it.
    from services.floorplan_process.geometry_extraction.yolo_detector import _detector
    _detector._load()
    if _detector._load_error:
        logger.warning("YOLO model failed to pre-load: %s", _detector._load_error)
    else:
        logger.info("YOLO model pre-loaded on %s", _detector._device)
    # Validate SMTP configuration and warn early if not set
    if not settings.smtp_from_email:
        logger.warning(
            "SMTP not configured (SMTP_FROM_EMAIL missing) — "
            "verification and password-reset emails will not be delivered. "
            "Set Gmail SMTP values in backend/.env.local to enable email delivery."
        )
    elif settings.smtp_username:
        logger.info("SMTP configured: %s:%d via %s", settings.smtp_host, settings.smtp_port, settings.smtp_username)
    else:
        logger.info("SMTP configured: %s:%d", settings.smtp_host, settings.smtp_port)


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await close_redis()


@app.get("/")
def read_root():
    return {"message": "BOQ to BSR RAG service is running."}


@app.get("/health")
def health_check():
    """Basic liveness probe — confirms the API process is alive."""
    return {
        "status": "ok",
        "env": settings.env,
        "smtp_configured": bool(settings.smtp_username and settings.smtp_password),
    }


@app.get("/healthz")
def healthz():
    """Liveness probe — returns 200 as long as the process is running."""
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    """Readiness probe — checks DB and Chroma connectivity."""
    checks: dict[str, str] = {}

    # PostgreSQL ping
    try:
        from infrastructure.data_layer.database.session import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as exc:
        logger.error("Readiness: postgres check failed: %s", exc)
        checks["postgres"] = "error"

    # Chroma ping
    try:
        from infrastructure.data_layer.vector_db.chroma_connection import get_chroma_client
        get_chroma_client().heartbeat()
        checks["chroma"] = "ok"
    except Exception as exc:
        logger.error("Readiness: chroma check failed: %s", exc)
        checks["chroma"] = "error"

    all_ok = all(v == "ok" for v in checks.values())
    status_code = 200 if all_ok else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ok" if all_ok else "degraded", "checks": checks},
    )
