"""Pipeline Diagnostic Monitor — development-only endpoints.

Exposes every pipeline step's full input/output for observability and debugging.

Routes
------
GET /api/pipeline/trace/{session_id}    — Live SSE stream of step records
GET /api/pipeline/snapshot/{session_id} — REST snapshot of the full trace
GET /api/pipeline/steps                 — Static step metadata registry
"""
import asyncio
import json

from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from app.api.state.session import process_store
from core.config.settings import settings


# Static registry of all pipeline steps in execution order.
# Used by the frontend to render step names/descriptions correctly.
_PIPELINE_STEPS = [
    {"index": 0,  "name": "extract_project_info",       "description": "Extract structured project info from user description via LLM"},
    {"index": 1,  "name": "check_requirements",          "description": "Verify MVED completeness and identify missing fields"},
    {"index": 2,  "name": "floorplan_download",          "description": "Download floor plan image from URL"},
    {"index": 3,  "name": "floorplan_cv",                "description": "Extract geometry (area, walls, openings) via Computer Vision"},
    {"index": 4,  "name": "baseline_boq",                "description": "LLM generates the initial BOQ item list (Stage 2)"},
    {"index": 5,  "name": "item_predictor_predictions",  "description": "ML predictor suggests candidate BOQ items (Stage 1)"},
    {"index": 6,  "name": "gap_fill",                    "description": "LLM gap-fill adds any items missed by baseline (Stage 3)"},
    {"index": 7,  "name": "bsr_matching",                "description": "RAG matches each BOQ item to a BSR rate via ChromaDB"},
    {"index": 8,  "name": "quantity_takeoff",            "description": "Compute quantities (geometry rules → ML predictor fallback)"},
    {"index": 9,  "name": "validation",                  "description": "Validate quantities, flag zero-rate and anomalous items"},
    {"index": 10, "name": "cost_calculation",            "description": "Compute item costs, preliminaries (8%), contingencies (5%)"},
    {"index": 11, "name": "transparency",                "description": "Score estimation confidence and collect defaults used"},
    {"index": 12, "name": "reporting",                   "description": "Assemble final report with rate-review items summary"},
]


def _dev_guard() -> None:
    """Defence-in-depth: refuse to serve if not in development environment."""
    if settings.env.lower() != "development":
        raise HTTPException(status_code=404, detail="Not found")


async def stream_pipeline_trace(session_id: str):
    """Live SSE stream of pipeline step records for a session.

    Flushes all steps already completed (catch-up), then streams new records
    as they arrive.  Closes automatically when the ``__done__`` sentinel is
    received from the pipeline.
    """
    _dev_guard()

    session = await process_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")


    async def event_generator():
        # 1. Flush any steps that already completed before we connected
        for record in list(session.pipeline_trace):
            yield f"event: step\ndata: {json.dumps(record, default=str)}\n\n"
            if record.get("step") == "__done__":
                return

        # 2. Stream new records live
        try:
            while True:
                try:
                    record = await asyncio.wait_for(session.trace_queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                yield f"event: step\ndata: {json.dumps(record, default=str)}\n\n"
                if record.get("step") == "__done__":
                    break
        except GeneratorExit:
            pass

    return StreamingResponse(event_generator(), media_type="text/event-stream")


async def get_pipeline_snapshot(session_id: str):
    """REST snapshot of the full pipeline trace for a session."""
    _dev_guard()

    session = await process_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    done = any(r.get("step") == "__done__" for r in session.pipeline_trace)
    return {
        "session_id": session_id,
        "status": "completed" if done else "in_progress",
        "step_count": len(session.pipeline_trace),
        "steps": session.pipeline_trace,
    }


async def get_pipeline_steps():
    """Static metadata registry of all pipeline steps."""
    _dev_guard()
    return {"steps": _PIPELINE_STEPS}
