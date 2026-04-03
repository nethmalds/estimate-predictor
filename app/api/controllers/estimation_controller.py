from chromadb.api.models.Collection import Collection
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from ai.rag.service import service
from data_layer.vector_db.chroma_connection import get_chroma_collection_dependency
from orchestration.estimation_workflow import run_estimation_workflow


class MatchRequest(BaseModel):
    boq_text: str = Field(..., min_length=3)


class IngestRequest(BaseModel):
    pdf_path: str


class EstimationRequest(BaseModel):
    description: str = Field(..., min_length=5)
    floorplan_image_path: str | None = None
    provided_parameters: dict | None = None




def match_boq(payload: MatchRequest):
    return service.match_boq_item(payload.boq_text)


def ingest_bsr(payload: IngestRequest):
    try:
        return service.ingest_bsr_pdf(payload.pdf_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def estimate_project(payload: EstimationRequest):
    try:
        return run_estimation_workflow(
            payload.description,
            floorplan_image_path=payload.floorplan_image_path,
            provided_parameters=payload.provided_parameters,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ImportError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc




def get_documents(
    collection: Collection = Depends(get_chroma_collection_dependency),
):
    try:
        total_count = collection.count()
        results = collection.get(limit=50, include=["documents", "metadatas"])
        ids = results.get("ids") or []
        documents = results.get("documents") or []
        metadatas = results.get("metadatas") or []

        items = [
            {
                "id": doc_id,
                "document": document,
                "metadata": metadata,
            }
            for doc_id, document, metadata in zip(ids, documents, metadatas)
        ]
        return {
            "count": len(items),
            "total_count": total_count,
            "items": items,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
