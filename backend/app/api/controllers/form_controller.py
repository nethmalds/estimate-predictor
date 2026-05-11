"""Form controller — thin HTTP adapter for the wizard estimation endpoints.

Pipeline orchestration logic has been moved to app.api.services.form_service.FormService.
Request schemas are imported from app.api.schemas.form_schemas.
"""
import asyncio
import json
import threading
from typing import Any

from fastapi import Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.schemas.form_schemas import WizardFormPayload, WizardValidateRequest
from app.api.services.form_service import FormService
from app.api.state.session import process_store
from app.api.state.run_registry import run_registry
from app.api.middleware.auth_dependency import get_current_user_id
from infrastructure.data_layer.database.session import get_db_session
from infrastructure.data_layer.database.models.estimate import Estimate
from services.clarification_process.service import (
    normalize_wizard_to_project_info,
    validate_wizard_payload,
    apply_defaults,
)


# ─── Endpoint handlers ────────────────────────────────────────────────────────

async def validate_form_payload(request: WizardValidateRequest):
    """POST /api/estimate-project/form/validate"""
    raw = request.payload.model_dump()
    errors = validate_wizard_payload(raw)
    if errors:
        return {"valid": False, "errors": errors}
    return {"valid": True, "errors": {}}


async def submit_form(
    payload: WizardFormPayload,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
):
    """POST /api/estimate-project/form/submit"""
    import uuid as _uuid

    raw = payload.model_dump()

    # Validate
    errors = validate_wizard_payload(raw)
    if errors:
        raise HTTPException(
            status_code=422,
            detail={"message": "Validation failed", "errors": errors},
        )

    # Normalize and apply Sri Lankan defaults
    project_info = apply_defaults(normalize_wizard_to_project_info(raw))

    description = payload.description or (
        f"{payload.building_type} building, {payload.floor_count} floor(s)"
    )

    try:
        uid = _uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user token.")

    # Create persisted Estimate record immediately, storing raw wizard payload.
    estimate_record = Estimate(
        user_id=uid,
        project_name=description,
        status="in_progress",
        project_info=project_info,
        wizard_payload=raw,
    )
    db.add(estimate_record)
    db.commit()
    db.refresh(estimate_record)
    estimate_id = str(estimate_record.id)

    # Create SSE session
    session = await process_store.create_session(
        description=description,
        floorplan_urls=payload.floorplan_urls,
        project_info=project_info,
        session_type="form",
    )

    # Create a cancel event for this run so it can be stopped later.
    cancel_event = threading.Event()

    # Fire pipeline in background and register in the run registry.
    task = asyncio.create_task(
        FormService.run_pipeline_and_complete(
            session,
            project_info,
            payload.floorplan_urls,
            estimate_id,
            cancel_event=cancel_event,
        )
    )
    run_registry.register(estimate_id, task, cancel_event, session.session_id)

    return {
        "session_id": session.session_id,
        "status": "processing",
        "estimate_id": estimate_id,
    }


async def stream_form_estimation(session_id: str):
    """GET /api/estimate-project/form/stream/{session_id}"""
    session = await process_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Form estimation session not found.")

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(session.queue.get(), timeout=20.0)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                yield _format_sse(event["event"], event["data"])
                if event["event"] in {"completed", "error", "cancelled"}:
                    break
        except GeneratorExit:
            pass

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _format_sse(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=True)
    return f"event: {event}\ndata: {payload}\n\n"
