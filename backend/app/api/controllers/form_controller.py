import asyncio
import json
import time
from typing import Any, Literal

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from services.clarification_process.clarification_agent import (
    normalize_wizard_to_project_info,
    validate_wizard_payload,
    apply_defaults,
)
from app.api.state.session import process_store
from application.pipelines.estimation_pipeline import run_estimation_pipeline_from_project_info



# ─── Pydantic request models ──────────────────────────────────────────────────

class FloorAreaRow(BaseModel):
    floor_label: str = Field(..., description="e.g. 'Ground Floor', 'First Floor'")
    area_value: float = Field(..., gt=0, description="Numeric area measurement")
    area_unit: str = Field(default="sqft", pattern="^(sqft|m2)$")


class WizardFormPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Step 1: Project basics
    building_type: Literal["residential", "commercial", "industrial"] = Field(...)
    floor_count: int = Field(..., ge=1, le=100)
    description: str | None = Field(default=None)
    floorplan_urls: list[str] = Field(default_factory=list)

    # Step 2: Floor areas
    floor_areas: list[FloorAreaRow] = Field(..., min_length=1)

    # Step 3: Building program — residential
    bedrooms: int | None = Field(default=None, ge=1, le=50)
    bathrooms: int | None = Field(default=None, ge=1, le=50)

    # Step 3: Building program — commercial
    primary_use_type: str | None = Field(default=None)
    washroom_count: int | None = Field(default=None, ge=1)

    # Step 3: Building program — industrial
    facility_type: str | None = Field(default=None)
    heavy_machinery_load: str | None = Field(default=None)
    hazardous_materials: str | None = Field(default=None)
    specialized_ventilation: str | None = Field(default=None)

    # Step 4: Construction details
    finish_level: str | None = None
    structural_system: str | None = None
    roof_type: str | None = None
    ceiling_type: str | None = None
    location: str | None = None
    soil_condition: str | None = None
    drainage_type: str | None = None
    external_works_scope: str | None = None


class WizardValidateRequest(BaseModel):
    payload: WizardFormPayload


# ─── Endpoint handlers ────────────────────────────────────────────────────────

async def validate_form_payload(request: WizardValidateRequest):
    """Validate a wizard form payload and return field-level errors."""
    raw = request.payload.model_dump()
    errors = validate_wizard_payload(raw)
    if errors:
        return {"valid": False, "errors": errors}
    return {"valid": True, "errors": {}}


async def submit_form(payload: WizardFormPayload):
    """Submit completed wizard form, create session, start estimation pipeline."""
    raw = payload.model_dump()

    # Validate
    errors = validate_wizard_payload(raw)
    if errors:
        raise HTTPException(
            status_code=422,
            detail={"message": "Validation failed", "errors": errors},
        )

    # Normalize to project_info structure
    project_info = normalize_wizard_to_project_info(raw)

    # Apply Sri Lankan defaults for any missing non-critical fields
    project_info = apply_defaults(project_info)

    description = payload.description or f"{payload.building_type} building, {payload.floor_count} floor(s)"

    # Create session
    session = await process_store.create_session(
        description=description,
        floorplan_urls=payload.floorplan_urls,
        project_info=project_info,
        session_type="form",
    )

    # Fire pipeline async
    asyncio.create_task(
        _run_pipeline_and_complete(session, project_info, payload.floorplan_urls)
    )


    return {"session_id": session.session_id, "status": "processing"}


async def stream_form_estimation(session_id: str):
    """SSE stream for form-submitted estimation session."""
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
                if event["event"] in {"completed", "error"}:
                    break
        except GeneratorExit:
            pass

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ─── Internal helpers ─────────────────────────────────────────────────────────

async def _run_pipeline_and_complete(session, project_info: dict, floorplan_urls: list[str]) -> None:
    try:
        loop = asyncio.get_running_loop()
        result = await asyncio.to_thread(
            run_estimation_pipeline_from_project_info,
            project_info,
            floorplan_urls=floorplan_urls,
            progress_callback=_build_progress_callback(session, loop),
        )
        _push_trace_sentinel(session)
        await session.queue.put({"event": "completed", "data": result})
    except Exception as exc:  # noqa: BLE001
        await session.queue.put({"event": "error", "data": {"message": str(exc)}})


def _build_progress_callback(session, loop: asyncio.AbstractEventLoop):
    def _progress(step: str, status: str, data: dict | None) -> None:
        if status == "trace_output":
            record = {
                "step": step,
                "status": "completed",
                "started_at": time.time(),
                "completed_at": time.time(),
                "duration_ms": 0.0,
                "output": data or {},
            }
            session.pipeline_trace.append(record)
            try:
                asyncio.run_coroutine_threadsafe(session.trace_queue.put(record), loop)
            except Exception:  # noqa: BLE001
                pass
            return

        event = {
            "event": "progress",
            "data": {"step": step, "status": status, **(data or {})},
        }
        try:
            asyncio.run_coroutine_threadsafe(session.queue.put(event), loop)
        except Exception:  # noqa: BLE001
            pass

    return _progress


def _push_trace_sentinel(session) -> None:
    sentinel = {"step": "__done__", "status": "done", "output": {}}
    session.pipeline_trace.append(sentinel)
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(session.trace_queue.put(sentinel), loop)
    except Exception:  # noqa: BLE001
        pass


def _format_sse(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=True)
    return f"event: {event}\ndata: {payload}\n\n"
