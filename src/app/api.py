from typing import Any

from chromadb.api.models.Collection import Collection
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from src.ai.rag.service import service
from src.data.vector_db.chroma_connection import get_chroma_collection_dependency

router = APIRouter()


class MatchRequest(BaseModel):
    boq_text: str = Field(..., min_length=3)


class IngestRequest(BaseModel):
    pdf_path: str


class ChromaDocumentBatchRequest(BaseModel):
    ids: list[str] = Field(..., min_length=1)
    documents: list[str] = Field(..., min_length=1)
    metadatas: list[dict[str, Any]] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_lengths(self):
        item_count = len(self.ids)
        if len(self.documents) != item_count or len(self.metadatas) != item_count:
            raise ValueError("ids, documents and metadatas must have the same length")
        return self


@router.post("/match-boq")
def match_boq(payload: MatchRequest):
    return service.match_boq_item(payload.boq_text)


@router.post("/ingest-bsr")
def ingest_bsr(payload: IngestRequest):
    try:
        return service.ingest_bsr_pdf(payload.pdf_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/api/documents/")
def add_documents(
    payload: ChromaDocumentBatchRequest,
    collection: Collection = Depends(get_chroma_collection_dependency),
):
    try:
        collection.add(
            ids=payload.ids,
            documents=payload.documents,
            metadatas=payload.metadatas,
        )
        return {
            "message": "Documents added successfully",
            "ids": payload.ids,
            "count": len(payload.ids),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
