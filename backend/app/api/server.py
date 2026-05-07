
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.rag_process.service import service
from app.api.routes.router import router as api_router
from app.api.state.session import process_store
from core.config.settings import settings
from core.exceptions.error_handlers import register_exception_handlers

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
    from services.rag_process.db import init_db
    init_db()
    service.bootstrap()
    process_store.start_cleanup()

@app.get("/")
def read_root():
    return {"message": "BOQ to BSR RAG service is running."}
