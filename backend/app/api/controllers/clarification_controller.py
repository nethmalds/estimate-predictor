import asyncio
import json
import re
import time
from typing import Any

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core.logging.logger import get_logger
from services.clarification_process.service import (
    extract_project_info,
    extract_project_info_with_clarifications,
)
from services.clarification_process.clarification_agent import (
    _REQUIRED_PARAMETER_FIELDS,
    build_clarification_questions,
    find_missing_fields,
    get_question_metadata,
    normalize_ceiling_type,
    validate_field_value,
    apply_defaults,
)
from app.api.state.session import process_store
from application.pipelines.estimation_pipeline import run_estimation_pipeline_from_project_info

_FINISH_LEVEL_OPTIONS = {
    "1": "standard",
    "2": "semi-luxury",
    "3": "full luxury",
}

logger = get_logger(__name__)


class ClarificationStartRequest(BaseModel):
    description: str = Field(..., min_length=5)
    floorplan_image_url: str | None = None


class ClarificationAnswerRequest(BaseModel):
    answer: str = Field(..., min_length=1)


async def start_clarification(payload: ClarificationStartRequest):
    try:
        project_info = await asyncio.to_thread(extract_project_info, payload.description)
        missing_fields = find_missing_fields(project_info)
        questions = build_clarification_questions(missing_fields)
        session = await process_store.create_session(
            description=payload.description,
            floorplan_image_url=payload.floorplan_image_url,
            project_info=project_info,
            missing_fields=missing_fields,
            questions=questions,
            session_type="clarification",
        )
        if missing_fields:
            first_field = missing_fields[0]
            await session.queue.put(
                {
                    "event": "question",
                    "data": {
                        "field": first_field,
                        "question": questions[0],
                        "metadata": get_question_metadata(first_field),
                        "remaining": len(missing_fields),
                    },
                }
            )
            return {
                "status": "session_started",
                "session_id": session.session_id,
                "needs_clarification": True,
            }

        await session.queue.put(
            {
                "event": "info",
                "data": {
                    "message": "Thanks! Preparing your estimate now. This usually takes about 10\u201320 seconds.",
                },
            }
        )
        asyncio.create_task(_run_pipeline_and_complete(session, project_info, payload.floorplan_image_url))
        return {
            "status": "session_started",
            "session_id": session.session_id,
            "needs_clarification": False,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


async def submit_clarification_answer(
    session_id: str,
    payload: ClarificationAnswerRequest,
):
    session = await process_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Clarification session not found.")

    # ── Confirmation flow ─────────────────────────────────────────────────────
    if session.awaiting_confirmation:
        response = payload.answer.strip().lower()
        if response not in {"yes", "no"}:
            await session.queue.put(
                {
                    "event": "question",
                    "data": {
                        "field": "confirmation",
                        "question": "Please answer yes or no.",
                        "metadata": {"input_type": "text"},
                    },
                }
            )
            return {"status": "awaiting_confirmation"}

        if response == "no":
            refreshed_info = await asyncio.to_thread(extract_project_info, session.description)
            session.project_info = refreshed_info
            session.answers = {}
            session.missing_fields = find_missing_fields(refreshed_info)
            session.questions = build_clarification_questions(session.missing_fields)
            session.current_index = 0
            session.awaiting_confirmation = False
            session.confirmed_project_info = None
            if session.missing_fields:
                first_field = session.missing_fields[0]
                await session.queue.put(
                    {
                        "event": "question",
                        "data": {
                            "field": first_field,
                            "question": session.questions[0],
                            "metadata": get_question_metadata(first_field),
                            "remaining": len(session.missing_fields),
                        },
                    }
                )
                return {"status": "needs_clarification"}

        confirmed_info = session.confirmed_project_info or session.project_info
        await session.queue.put(
            {
                "event": "info",
                "data": {
                    "message": "Thanks! Preparing your estimate now. This usually takes about 10\u201320 seconds.",
                },
            }
        )
        session.awaiting_confirmation = False
        session.confirmed_project_info = None
        asyncio.create_task(_run_pipeline_and_complete(session, confirmed_info, session.floorplan_image_url))
        return {"status": "processing"}

    if session.current_index >= len(session.missing_fields):
        return {"status": "completed"}

    field = session.missing_fields[session.current_index]
    raw_answer = payload.answer.strip()

    # ── Parse the raw answer ───────────────────────────────────────────────────
    parsed_value = _parse_answer(field, raw_answer)

    # ── Validate the parsed value (C2: invalid value detection) ───────────────
    validation_error = validate_field_value(field, parsed_value)
    if validation_error:
        logger.warning(
            "clarification_invalid_value session_id=%s field=%s value=%r error=%s",
            session.session_id,
            field,
            raw_answer,
            validation_error,
        )
        # Push an error event so the frontend displays an inline amber banner
        await session.queue.put(
            {
                "event": "validation_error",
                "data": {
                    "field": field,
                    "message": f"\u26a0\ufe0f {validation_error}",
                },
            }
        )
        # Re-ask the same question without advancing the index
        await session.queue.put(
            {
                "event": "question",
                "data": {
                    "field": field,
                    "question": session.questions[session.current_index],
                    "metadata": get_question_metadata(field),
                    "remaining": len(session.missing_fields) - session.current_index,
                },
            }
        )
        return {"status": "invalid_value", "field": field, "error": validation_error}

    # ── Apply the valid answer ─────────────────────────────────────────────────
    _apply_answer_to_project_info(session.project_info, field, raw_answer, parsed_value)
    resolved_value = _get_project_info_value(session.project_info, field)
    if resolved_value is not None:
        session.answers[field] = resolved_value
    else:
        session.answers[field] = raw_answer

    logger.info(
        "clarification_answer session_id=%s field=%s value=%r index=%d",
        session.session_id,
        field,
        session.answers.get(field),
        session.current_index,
    )
    session.current_index += 1

    # ── More questions to ask? ─────────────────────────────────────────────────
    if session.current_index < len(session.missing_fields):
        next_field = session.missing_fields[session.current_index]
        next_question = session.questions[session.current_index]
        await session.queue.put(
            {
                "event": "question",
                "data": {
                    "field": next_field,
                    "question": next_question,
                    "metadata": get_question_metadata(next_field),
                    "remaining": len(session.missing_fields) - session.current_index,
                },
            }
        )
        return {"status": "awaiting_clarification"}

    # ── All answers collected — re-parse with LLM + validate (C4) ─────────────
    clarified_info = await asyncio.to_thread(
        extract_project_info_with_clarifications,
        session.description,
        session.answers,
    )
    _merge_required_fields(clarified_info, session.project_info, _REQUIRED_PARAMETER_FIELDS)

    # C4: validate the LLM's re-parsed output; re-enter loop if still missing
    remaining_fields = find_missing_fields(clarified_info)
    if remaining_fields:
        session.project_info = clarified_info
        session.missing_fields = remaining_fields
        session.questions = build_clarification_questions(remaining_fields)
        session.current_index = 0
        first_field = remaining_fields[0]
        await session.queue.put(
            {
                "event": "question",
                "data": {
                    "field": first_field,
                    "question": session.questions[0],
                    "metadata": get_question_metadata(first_field),
                    "remaining": len(remaining_fields),
                },
            }
        )
        return {"status": "needs_clarification"}

    session.awaiting_confirmation = True
    session.confirmed_project_info = clarified_info
    summary = _build_confirmation_summary(clarified_info)
    await session.queue.put(
        {
            "event": "question",
            "data": {"field": "confirmation", "question": summary, "metadata": {"input_type": "text"}},
        }
    )
    return {"status": "awaiting_confirmation"}


async def _run_pipeline_and_complete(session, project_info: dict, floorplan_image_url: str | None) -> None:
    # Apply Sri Lankan defaults for non-MVED fields before running the pipeline
    project_info = apply_defaults(project_info)
    try:
        loop = asyncio.get_running_loop()
        result = await asyncio.to_thread(
            run_estimation_pipeline_from_project_info,
            project_info,
            floorplan_image_url=floorplan_image_url,
            progress_callback=_build_progress_callback(session, loop),
        )
        # Push __done__ sentinel to trace_queue for diagnostic SSE subscribers
        _push_trace_sentinel(session)
        await session.queue.put({"event": "completed", "data": result})
        logger.info("session_end session_id=%s type=clarification", session.session_id)
    except Exception as exc:  # noqa: BLE001
        await session.queue.put({"event": "error", "data": {"message": str(exc)}})
        logger.exception("session_error session_id=%s type=clarification", session.session_id)


def _build_progress_callback(session, loop: asyncio.AbstractEventLoop) -> callable:
    """Build the progress callback that feeds both the SSE queue and the pipeline trace."""

    def _progress(step: str, status: str, data: dict | None) -> None:
        # dev_log events carry large data — record in trace only, not SSE
        if status == "dev_log":
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

        logger.info(
            "clarification_progress step=%s status=%s session_id=%s",
            step,
            status,
            session.session_id,
        )
        event = {
            "event": "progress",
            "data": {"step": step, "status": status, **(data or {})},
        }
        try:
            asyncio.run_coroutine_threadsafe(session.queue.put(event), loop)
        except Exception:  # noqa: BLE001
            logger.warning(
                "progress_callback_failed step=%s session_id=%s",
                step,
                session.session_id,
            )

    return _progress


def _push_trace_sentinel(session) -> None:
    """Push the __done__ sentinel to trace_queue so SSE trace stream closes cleanly."""
    sentinel = {"step": "__done__", "status": "done", "output": {}}
    session.pipeline_trace.append(sentinel)
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(session.trace_queue.put(sentinel), loop)
    except Exception:  # noqa: BLE001
        pass


async def stream_clarification(session_id: str):
    session = await process_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Clarification session not found.")

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(session.queue.get(), timeout=20.0)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                logger.info(
                    "session_event session_id=%s type=clarification event=%s",
                    session.session_id,
                    event["event"],
                )
                yield _format_sse(event["event"], event["data"])
                if event["event"] in {"completed", "error"}:
                    break
        except GeneratorExit:
            # R7: client disconnected — mark session done to prevent memory build-up
            logger.info(
                "sse_disconnect session_id=%s type=clarification",
                session.session_id,
            )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


def _format_sse(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=True)
    return f"event: {event}\ndata: {payload}\n\n"


def _parse_answer(field: str, raw_answer: str) -> Any:
    """Parse a raw string answer into its natural type for the given field."""
    if field in {"floors", "bedrooms", "bathrooms"}:
        return _parse_int(raw_answer)
    if field == "built_up_area":
        # C3: area_picker returns canonical values like "1750 sqft" — pass through directly.
        # For custom text try to parse; if not parseable, return None so server re-asks.
        cleaned = raw_answer.strip()
        # If it already has a unit suffix it came from the area_picker widget — use as-is
        if re.search(r"(sqft|sq\s*ft|m2|m\u00b2)", cleaned, re.IGNORECASE):
            return cleaned
        # Otherwise try to parse as a bare number
        parsed = _parse_int(cleaned)
        return str(parsed) if parsed else None
    if field == "finish_level":
        return _normalize_finish_level(raw_answer)
    if field == "ceiling_type":
        return normalize_ceiling_type(raw_answer) or raw_answer.strip().lower() or None
    return raw_answer.strip() or None


def _apply_answer_to_project_info(
    project_info: dict, field: str, raw_answer: str, parsed_value: Any = None
) -> None:
    """Write the parsed value into the correct location in project_info."""
    value = parsed_value if parsed_value is not None else raw_answer.strip() or None

    if field == "floors":
        project_info["floors"] = value
        return

    parameters = project_info.get("parameters") or {}
    parameters[field] = value
    project_info["parameters"] = parameters


def _parse_int(value: str) -> int | None:
    match = re.search(r"-?\d+", value)
    if not match:
        return None
    try:
        return int(match.group(0))
    except ValueError:
        return None


def _normalize_finish_level(value: str) -> str | None:
    normalized = value.strip().lower()
    if not normalized:
        return None
    if normalized in {"standard", "standard / budget", "budget"}:
        return "standard"
    if normalized in {"semi-luxury", "semi luxury", "semi"}:
        return "semi-luxury"
    if normalized in {"full luxury", "luxury", "full"}:
        return "full luxury"
    match = re.search(r"\b([1-3])\b", normalized)
    if match:
        return _FINISH_LEVEL_OPTIONS.get(match.group(1))
    return normalized


def _get_project_info_value(project_info: dict, field: str) -> Any:
    if field == "floors":
        return project_info.get("floors")
    parameters = project_info.get("parameters") or {}
    return parameters.get(field)


def _merge_required_fields(target: dict, source: dict, required_param_fields: list[str]) -> None:
    """Merge missing required fields from *source* into *target* (C4/Q5 fix).

    Uses the authoritative ``_REQUIRED_PARAMETER_FIELDS`` from
    ``clarification_agent.py`` instead of a separate hardcoded list.
    """
    if target.get("floors") is None and source.get("floors") is not None:
        target["floors"] = source.get("floors")

    target_parameters = target.get("parameters") or {}
    source_parameters = source.get("parameters") or {}
    for field in required_param_fields:
        if target_parameters.get(field) is None and source_parameters.get(field) is not None:
            target_parameters[field] = source_parameters.get(field)
    target["parameters"] = target_parameters


def _build_confirmation_summary(project_info: dict) -> str:
    parameters = project_info.get("parameters") or {}
    floors = project_info.get("floors") or "unknown"
    bedrooms = parameters.get("bedrooms") or "unknown"
    bathrooms = parameters.get("bathrooms") or "unknown"
    built_up_area = parameters.get("built_up_area") or "unknown"
    finish_level = parameters.get("finish_level") or "unknown"
    roof_type = parameters.get("roof_type") or "unknown"
    ceiling_type = parameters.get("ceiling_type") or "unknown"
    return (
        "Please confirm these details:\n"
        f"- Floors: {floors}\n"
        f"- Bedrooms: {bedrooms}\n"
        f"- Bathrooms: {bathrooms}\n"
        f"- Built-up area: {built_up_area}\n"
        f"- Finish level: {finish_level}\n"
        f"- Roof type: {roof_type}\n"
        f"- Ceiling type: {ceiling_type}\n"
        "Reply with yes or no."
    )
