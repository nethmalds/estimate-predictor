from fastapi import FastAPI

from src.ai.rag.service import service
from src.app.api import router as rag_router

app = FastAPI()
app.include_router(rag_router)


@app.on_event("startup")
def startup_event() -> None:
    service.bootstrap()

@app.get("/")
def read_root():
    return {"message": "BOQ to BSR RAG service is running."}
