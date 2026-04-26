import asyncio
import json
import re
from typing import Any

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core.logging.logger import get_logger
from services.clarification_process.clarification_agent import build_clarification_questions, find_missing_fields, normalize_ceiling_type
from services.clarification_process.llm_client import (
    extract_project_info,
    extract_project_info_with_clarifications,
)
from app.api.state.session import process_store
from application.pipelines.estimation_pipeline import run_estimation_pipeline_from_project_info

_BASELINE_BUILT_UP_AREA = 1800
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
            await _queue_progress(
                session,
                "clarification_question",
                "pending",
                {
                    "field": missing_fields[0],
                    "question": questions[0],
                    "remaining": len(missing_fields),
                },
            )
            await session.queue.put(
                {
                    "event": "question",
                    "data": {"field": missing_fields[0], "question": questions[0]},
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
                    "message": "Thanks! Preparing your estimate now. This usually takes about 10-20 seconds.",
                },
            }
        )
        await _queue_progress(session, "clarification_complete", "skipped", None)
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

    if session.awaiting_confirmation:
        response = payload.answer.strip().lower()
        if response not in {"yes", "no"}:
            logger.info(
                "session_event session_id=%s type=clarification event=confirmation_invalid",
                session.session_id,
            )
            await session.queue.put(
                {
                    "event": "question",
                    "data": {
                        "field": "confirmation",
                        "question": "Please answer yes or no.",
                    },
                }
            )
            return {"status": "awaiting_confirmation"}

        if response == "no":
            logger.info(
                "session_event session_id=%s type=clarification event=confirmation_rejected",
                session.session_id,
            )
            await _queue_progress(session, "clarification_confirmation", "rejected", None)
            refreshed_info = await asyncio.to_thread(extract_project_info, session.description)
            session.project_info = refreshed_info
            session.answers = {}
            session.missing_fields = find_missing_fields(refreshed_info)
            session.questions = build_clarification_questions(session.missing_fields)
            session.current_index = 0
            session.awaiting_confirmation = False
            session.confirmed_project_info = None
            if session.missing_fields:
                logger.info(
                    "session_event session_id=%s type=clarification event=question",
                    session.session_id,
                )
                await _queue_progress(
                    session,
                    "clarification_question",
                    "pending",
                    {
                        "field": session.missing_fields[0],
                        "question": session.questions[0],
                        "remaining": len(session.missing_fields),
                    },
                )
                await session.queue.put(
                    {
                        "event": "question",
                        "data": {
                            "field": session.missing_fields[0],
                            "question": session.questions[0],
                        },
                    }
                )
                return {"status": "needs_clarification"}

        confirmed_info = session.confirmed_project_info or session.project_info
        logger.info(
            "session_event session_id=%s type=clarification event=confirmation_accepted",
            session.session_id,
        )
        await _queue_progress(session, "clarification_confirmation", "accepted", None)
        await session.queue.put(
            {
                "event": "info",
                "data": {
                    "message": "Thanks! Preparing your estimate now. This usually takes about 10-20 seconds.",
                },
            }
        )
        session.awaiting_confirmation = False
        session.confirmed_project_info = None
        asyncio.create_task(_run_pipeline_and_complete(session, confirmed_info, session.floorplan_image_url))
        return {"status": "processing"}

    if session.current_index >= len(session.missing_fields):
        logger.info(
            "session_event session_id=%s type=clarification event=completed",
            session.session_id,
        )
        return {"status": "completed"}

    field = session.missing_fields[session.current_index]
    raw_answer = payload.answer.strip()
    session.answers[field] = raw_answer
    _apply_answer_to_project_info(session.project_info, field, raw_answer)
    normalized_value = _get_project_info_value(session.project_info, field)
    if normalized_value is not None:
        session.answers[field] = normalized_value
    await _queue_progress(
        session,
        "clarification_answer",
        "received",
        {
            "field": field,
            "value": session.answers.get(field),
            "index": session.current_index,
        },
    )
    session.current_index += 1

    if session.current_index < len(session.missing_fields):
        next_field = session.missing_fields[session.current_index]
        next_question = session.questions[session.current_index]
        logger.info(
            "session_event session_id=%s type=clarification event=question",
            session.session_id,
        )
        await _queue_progress(
            session,
            "clarification_question",
            "pending",
            {
                "field": next_field,
                "question": next_question,
                "remaining": len(session.missing_fields) - session.current_index,
            },
        )
        await session.queue.put(
            {"event": "question", "data": {"field": next_field, "question": next_question}}
        )
        return {"status": "awaiting_clarification"}

    clarified_info = await asyncio.to_thread(
        extract_project_info_with_clarifications,
        session.description,
        session.answers,
    )
    _merge_required_fields(clarified_info, session.project_info)
    remaining_fields = find_missing_fields(clarified_info)
    if remaining_fields:
        session.project_info = clarified_info
        session.missing_fields = remaining_fields
        session.questions = build_clarification_questions(remaining_fields)
        session.current_index = 0
        logger.info(
            "session_event session_id=%s type=clarification event=question",
            session.session_id,
        )
        await _queue_progress(
            session,
            "clarification_question",
            "pending",
            {
                "field": remaining_fields[0],
                "question": session.questions[0],
                "remaining": len(remaining_fields),
            },
        )
        await session.queue.put(
            {
                "event": "question",
                "data": {"field": remaining_fields[0], "question": session.questions[0]},
            }
        )
        return {"status": "needs_clarification"}

    session.awaiting_confirmation = True
    session.confirmed_project_info = clarified_info
    summary = _build_confirmation_summary(clarified_info)
    logger.info(
        "session_event session_id=%s type=clarification event=confirmation_requested",
        session.session_id,
    )
    await _queue_progress(
        session,
        "clarification_confirmation",
        "pending",
        None,
    )
    await session.queue.put(
        {
            "event": "question",
            "data": {"field": "confirmation", "question": summary},
        }
    )
    return {"status": "awaiting_confirmation"}


async def _run_pipeline_and_complete(session, project_info: dict, floorplan_image_url: str | None) -> None:
    try:
        result = await asyncio.to_thread(
            run_estimation_pipeline_from_project_info,
            project_info,
            floorplan_image_url=floorplan_image_url,
            progress_callback=_build_progress_callback(session),
        )
        await session.queue.put({"event": "completed", "data": result})
        logger.info("session_end session_id=%s type=clarification", session.session_id)
    except Exception as exc:  # noqa: BLE001
        await session.queue.put({"event": "error", "data": {"message": str(exc)}})
        logger.exception("session_error session_id=%s type=clarification", session.session_id)


def _build_progress_callback(session) -> callable:
    import asyncio
    loop = asyncio.get_event_loop()

    def _progress(step: str, status: str, data: dict | None) -> None:
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
        asyncio.run_coroutine_threadsafe(session.queue.put(event), loop)

    return _progress


async def _queue_progress(session, step: str, status: str, data: dict | None) -> None:
    logger.info(
        "clarification_progress step=%s status=%s session_id=%s",
        step,
        status,
        session.session_id,
    )


async def stream_clarification(session_id: str):
    session = await process_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Clarification session not found.")

    async def event_generator():
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

    return StreamingResponse(event_generator(), media_type="text/event-stream")


def _format_sse(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=True)
    return f"event: {event}\ndata: {payload}\n\n"


def _apply_answer_to_project_info(project_info: dict, field: str, answer: str) -> None:
    value: Any = answer.strip() or None
    if field in {"floors", "bedrooms", "bathrooms"}:
        value = _parse_int(answer)
    if field == "built_up_area":
        value = _parse_int(answer)
        if value is None:
            value = _BASELINE_BUILT_UP_AREA
        value = str(value)
    if field == "finish_level":
        value = _normalize_finish_level(answer)
    if field == "ceiling_type":
        value = normalize_ceiling_type(answer) or answer.strip().lower() or None

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


def _merge_required_fields(target: dict, source: dict) -> None:
    required_parameters = {"bedrooms", "bathrooms", "built_up_area", "finish_level", "roof_type", "ceiling_type"}
    if not target.get("floors") and source.get("floors"):
        target["floors"] = source.get("floors")

    target_parameters = target.get("parameters") or {}
    source_parameters = source.get("parameters") or {}
    for field in required_parameters:
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


