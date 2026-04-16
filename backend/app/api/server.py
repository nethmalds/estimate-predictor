from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from infrastructure.ai.rag.service import service
from app.api.routes.router import router as api_router
from core.config.settings import settings
from core.exceptions.error_handlers import register_exception_handlers
from core.logging.logger import get_logger, setup_logging

setup_logging(settings.log_level)
logger = get_logger(__name__)

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
def startup_event() -> None:
    logger.info("API startup initiated")
    service.bootstrap()

@app.get("/")
def read_root():
    return {"message": "BOQ to BSR RAG service is running."}
