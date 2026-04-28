import asyncio
import json
from typing import Any

from chromadb.api.models.Collection import Collection
from fastapi import Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core.logging.logger import get_logger
from services.rag_process.service import service
from services.rag_process.retriever import retrieve_candidates, extract_query_features, clean_boq_query
from services.rag_process.scorer import score_candidate
from infrastructure.data_layer.vector_db.chroma_connection import get_chroma_collection_dependency
from application.pipelines.estimation_pipeline import run_estimation_pipeline
from app.api.state.session import process_store
from core.config.settings import settings
from infrastructure.data_layer.database.session import SessionLocal


class MatchRequest(BaseModel):
    boq_text: str = Field(..., min_length=3)


class IngestRequest(BaseModel):
    pdf_path: str


class EstimationStreamStartRequest(BaseModel):
    description: str = Field(..., min_length=5)
    floorplan_image_url: str | None = None


class DiagnoseRequest(BaseModel):
    descriptions: list[str] = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


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


def diagnose_bsr(payload: DiagnoseRequest):
    """Diagnostic endpoint: returns top BSR candidates + raw scores for each BOQ description.

    POST /api/rag/diagnose
    Body: { "descriptions": ["...", "..."], "top_k": 5 }
    Response: list of { description, cleaned_text, top_candidates: [{item_no, description, vector_score,
                keyword_score, final_score, match_type}] }
    """
    results = []
    try:
        with SessionLocal() as db:
            for desc in payload.descriptions:
                query_features = extract_query_features(desc)
                cleaned_text = clean_boq_query(query_features.normalized_text)

                query_features_obj, candidates = retrieve_candidates(
                    boq_text=desc,
                    session=db,
                    vector_store=service._get_vector_store(),
                    embedder=service._get_embedder(),
                    top_k=payload.top_k,
                )

                scored_candidates = []
                for cand in candidates:
                    bsr_item = cand["bsr_item"]
                    scores = score_candidate(query_features_obj, bsr_item, cand["vector_score"])
                    SOFT = 0.30
                    CONFIRM = settings.min_confidence_threshold
                    fs = scores["final_score"]
                    if fs < SOFT:
                        mt = "no_match"
                    elif fs < CONFIRM:
                        mt = "soft_match"
                    else:
                        mt = "confirmed"
                    scored_candidates.append(
                        {
                            "item_no": bsr_item.item_no,
                            "bsr_description": bsr_item.description,
                            "unit": bsr_item.unit,
                            "rate": bsr_item.rate,
                            "vector_score": scores["vector_score"],
                            "keyword_score": scores["keyword_score"],
                            "final_score": scores["final_score"],
                            "match_type": mt,
                            "matched_fields": scores["matched_fields"],
                        }
                    )

                scored_candidates.sort(key=lambda x: x["final_score"], reverse=True)

                results.append(
                    {
                        "description": desc,
                        "cleaned_text": cleaned_text,
                        "detected_work_type": query_features.work_type,
                        "detected_material": query_features.material,
                        "top_candidates": scored_candidates,
                    }
                )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"count": len(results), "results": results}


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
    import asyncio
    loop = asyncio.get_event_loop()

    def _progress(step: str, status: str, data: dict | None) -> None:
        # "dev_log" events carry large data dumps — they go to payloads.log only,
        # never over SSE to the client.
        if status == "dev_log":
            return
        logger.info(
            "estimation_progress step=%s status=%s session_id=%s",
            step,
            status,
            session.session_id,
        )
        event = {
            "event": "progress",
            "data": {"step": step, "status": status, **(data or {})},
        }
        asyncio.run_coroutine_threadsafe(session.queue.put(event), loop)

    return _progress


def _format_sse(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=True)
    return f"event: {event}\ndata: {payload}\n\n"
