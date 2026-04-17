import asyncio
import json
from typing import Any

from chromadb.api.models.Collection import Collection
from fastapi import Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core.logging.logger import get_logger
from services.rag_process.service import service
from infrastructure.data_layer.vector_db.chroma_connection import get_chroma_collection_dependency
from application.pipelines.estimation_pipeline import run_estimation_pipeline
from app.api.state.session import process_store


class MatchRequest(BaseModel):
    boq_text: str = Field(..., min_length=3)


class IngestRequest(BaseModel):
    pdf_path: str


class EstimationStreamStartRequest(BaseModel):
    description: str = Field(..., min_length=5)
    floorplan_image_url: str | None = None


logger = get_logger(__name__)




def match_boq(payload: MatchRequest):
    return service.match_boq_item(payload.boq_text)


def ingest_bsr(payload: IngestRequest):
    try:
        return service.ingest_bsr_pdf(payload.pdf_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


async def start_estimation_stream(payload: EstimationStreamStartRequest):
    session = await process_store.create_session(
        description=payload.description,
        floorplan_image_url=payload.floorplan_image_url,
        session_type="estimation",
    )
    logger.info(
        "session_event session_id=%s type=estimation event=started",
        session.session_id,
    )
    await session.queue.put(
        {
            "event": "info",
            "data": {
                "message": "Starting estimation. You will receive step updates shortly.",
            },
        }
    )
    asyncio.create_task(_run_estimation_stream(session))
    return {
        "status": "session_started",
        "session_id": session.session_id,
    }


async def stream_estimation(session_id: str):
    session = await process_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Estimation session not found.")

    async def event_generator():
        while True:
            try:
                event = await asyncio.wait_for(session.queue.get(), timeout=20.0)
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
                continue
            logger.info(
                "session_event session_id=%s type=estimation event=%s",
                session.session_id,
                event["event"],
            )
            yield _format_sse(event["event"], event["data"])
            if event["event"] in {"completed", "error"}:
                break

    return StreamingResponse(event_generator(), media_type="text/event-stream")


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


async def _run_estimation_stream(session) -> None:
    try:
        result = await asyncio.to_thread(
            run_estimation_pipeline,
            session.description,
            floorplan_image_url=session.floorplan_image_url,
            progress_callback=_build_progress_callback(session),
        )
        if isinstance(result, dict) and result.get("status") == "needs_clarification":
            await session.queue.put(
                {
                    "event": "error",
                    "data": {
                        "message": "More information is required before an estimate can be produced. "
                        "Please use the clarification endpoint.",
                        "question": result.get("question"),
                    },
                }
            )
            logger.info("session_needs_clarification session_id=%s type=estimation", session.session_id)
        else:
            await session.queue.put({"event": "completed", "data": result})
            logger.info("session_end session_id=%s type=estimation", session.session_id)
    except Exception as exc:  # noqa: BLE001 - preserve error details
        await session.queue.put({"event": "error", "data": {"message": str(exc)}})
        logger.exception("session_error session_id=%s type=estimation", session.session_id)


def _build_progress_callback(session) -> callable:
    def _progress(step: str, status: str, data: dict | None) -> None:
        logger.info(
            "estimation_progress step=%s status=%s session_id=%s",
            step,
            status,
            session.session_id,
        )

    return _progress


def _format_sse(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=True)
    return f"event: {event}\ndata: {payload}\n\n"
