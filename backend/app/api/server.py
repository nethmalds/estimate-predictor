from core.logging.logger import ensure_logging

# Initialise the three-file logging system before any service module is imported.
# This guarantees that every logger created during module-level code (e.g.
# `logger = get_logger(__name__)` at the top of service files) already has its
# file handler attached, so no early messages are lost.
ensure_logging()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.rag_process.service import service
from app.api.routes.router import router as api_router
from app.api.middleware.request_logging import RequestLoggingMiddleware
from app.api.state.session import process_store
from core.config.settings import settings
from core.exceptions.error_handlers import register_exception_handlers
from core.logging.logger import get_logger
logger = get_logger(__name__)

app = FastAPI()
app.add_middleware(RequestLoggingMiddleware)
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
def startup_event() -> None:
    logger.info("API startup initiated")
    service.bootstrap()
    process_store.start_cleanup()

@app.get("/")
def read_root():
    return {"message": "BOQ to BSR RAG service is running."}
