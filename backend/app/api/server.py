
import asyncio
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.rag_process.service import service
from app.api.routes.router import router as api_router
from app.api.state.session import process_store
from core.config.settings import settings
from core.exceptions.error_handlers import register_exception_handlers

logger = logging.getLogger(__name__)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_exception_handlers(app)
app.include_router(api_router)


@app.on_event("startup")
async def startup_event() -> None:
    from services.rag_process.service import init_db
    # Run Alembic migrations synchronously (fast, ~1-2s)
    init_db()
    # Start session cleanup loop
    process_store.start_cleanup()
    # Validate SMTP configuration and warn early if not set
    if not settings.smtp_username or not settings.smtp_password:
        logger.warning(
            "SMTP not configured (SMTP_USERNAME/SMTP_PASSWORD missing). "
            "Forgot-password emails will not be delivered. "
            "Set SMTP credentials in backend/.env.local to enable Gmail delivery."
        )
    else:
        logger.info("SMTP configured: %s:%d via %s", settings.smtp_host, settings.smtp_port, settings.smtp_username)
    # Bootstrap Chroma/RAG in background — avoids blocking uvicorn startup
    # (Chroma HttpClient cold-start can take 60-90s on first connection)
    asyncio.create_task(_bootstrap_services())


async def _bootstrap_services() -> None:
    """Initialize Chroma and RAG service in a background task.

    Running this in a background task allows uvicorn to mark the app as
    ready immediately instead of waiting for the Chroma cold-start.
    """
    await asyncio.to_thread(service.bootstrap)


@app.get("/")
def read_root():
    return {"message": "BOQ to BSR RAG service is running."}


@app.get("/health")
def health_check():
    """Basic readiness probe — confirms the API process is alive."""
    return {
        "status": "ok",
        "env": settings.env,
        "smtp_configured": bool(settings.smtp_username and settings.smtp_password),
    }
