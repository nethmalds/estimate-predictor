import json
import re
from typing import Any

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from infrastructure.ai.llm.clarification_agent import build_clarification_questions, find_missing_fields
from infrastructure.ai.llm.llm_client import (
    extract_project_info,
    extract_project_info_with_clarifications,
)
from app.api.controllers.clarification_session import clarification_store
from application.pipelines.estimation_pipeline import run_estimation_pipeline_from_project_info

_BASELINE_BUILT_UP_AREA = 1800
_FINISH_LEVEL_OPTIONS = {
    "1": "standard",
    "2": "semi-luxury",
    "3": "full luxury",
}


class ClarificationStartRequest(BaseModel):
    description: str = Field(..., min_length=5)
    floorplan_image_url: str | None = None


class ClarificationAnswerRequest(BaseModel):
    answer: str = Field(..., min_length=1)


async def start_clarification(payload: ClarificationStartRequest):
    try:
        project_info = extract_project_info(payload.description)
        missing_fields = find_missing_fields(project_info)
        if not missing_fields:
            result = run_estimation_pipeline_from_project_info(
                project_info,
                floorplan_image_url=payload.floorplan_image_url,
            )
            return {"status": "estimated", "result": result}

        questions = build_clarification_questions(missing_fields)
        session = await clarification_store.create_session(
            description=payload.description,
            floorplan_image_url=payload.floorplan_image_url,
            project_info=project_info,
            missing_fields=missing_fields,
            questions=questions,
        )
        await session.queue.put(
            {
                "event": "question",
                "data": {"field": missing_fields[0], "question": questions[0]},
            }
        )
        return {"status": "needs_clarification", "session_id": session.session_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


async def submit_clarification_answer(
    session_id: str,
    payload: ClarificationAnswerRequest,
):
    session = await clarification_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Clarification session not found.")

    if session.awaiting_confirmation:
        response = payload.answer.strip().lower()
        if response not in {"yes", "no"}:
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
            refreshed_info = extract_project_info(session.description)
            session.project_info = refreshed_info
            session.answers = {}
            session.missing_fields = find_missing_fields(refreshed_info)
            session.questions = build_clarification_questions(session.missing_fields)
            session.current_index = 0
            session.awaiting_confirmation = False
            session.confirmed_project_info = None
            if session.missing_fields:
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
        await session.queue.put(
            {
                "event": "info",
                "data": {
                    "message": "Thanks! Preparing your estimate now. This usually takes about 10-20 seconds.",
                },
            }
        )
        result = run_estimation_pipeline_from_project_info(
            confirmed_info,
            floorplan_image_url=session.floorplan_image_url,
        )
        await session.queue.put({"event": "completed", "data": result})
        session.awaiting_confirmation = False
        session.confirmed_project_info = None
        return {"status": "processing"}

    if session.current_index >= len(session.missing_fields):
        return {"status": "completed"}

    field = session.missing_fields[session.current_index]
    raw_answer = payload.answer.strip()
    session.answers[field] = raw_answer
    _apply_answer_to_project_info(session.project_info, field, raw_answer)
    normalized_value = _get_project_info_value(session.project_info, field)
    if normalized_value is not None:
        session.answers[field] = normalized_value
    session.current_index += 1

    if session.current_index < len(session.missing_fields):
        next_field = session.missing_fields[session.current_index]
        next_question = session.questions[session.current_index]
        await session.queue.put(
            {"event": "question", "data": {"field": next_field, "question": next_question}}
        )
        return {"status": "awaiting_clarification"}

    clarified_info = extract_project_info_with_clarifications(
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
    await session.queue.put(
        {
            "event": "question",
            "data": {"field": "confirmation", "question": summary},
        }
    )
    return {"status": "awaiting_confirmation"}


async def stream_clarification(session_id: str):
    session = await clarification_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Clarification session not found.")

    async def event_generator():
        try:
            while True:
                event = await session.queue.get()
                yield _format_sse(event["event"], event["data"])
                if event["event"] == "completed":
                    break
        finally:
            await clarification_store.delete_session(session_id)

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
    required_parameters = {"bedrooms", "bathrooms", "built_up_area", "finish_level", "roof_type"}
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
    return (
        "Please confirm these details:\n"
        f"- Floors: {floors}\n"
        f"- Bedrooms: {bedrooms}\n"
        f"- Bathrooms: {bathrooms}\n"
        f"- Built-up area: {built_up_area}\n"
        f"- Finish level: {finish_level}\n"
        f"- Roof type: {roof_type}\n"
        "Reply with yes or no."
    )
