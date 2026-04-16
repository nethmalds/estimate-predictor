import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ClarificationSession:
    session_id: str
    created_at: float
    description: str
    floorplan_image_url: str | None
    project_info: dict
    missing_fields: list[str]
    questions: list[str]
    answers: dict[str, Any] = field(default_factory=dict)
    current_index: int = 0
    awaiting_confirmation: bool = False
    confirmed_project_info: dict | None = None
    queue: asyncio.Queue[dict[str, Any]] = field(default_factory=asyncio.Queue)


class ClarificationSessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, ClarificationSession] = {}
        self._lock = asyncio.Lock()

    async def create_session(
        self,
        description: str,
        floorplan_image_url: str | None,
        project_info: dict,
        missing_fields: list[str],
        questions: list[str],
    ) -> ClarificationSession:
        session_id = uuid.uuid4().hex
        session = ClarificationSession(
            session_id=session_id,
            created_at=time.time(),
            description=description,
            floorplan_image_url=floorplan_image_url,
            project_info=project_info,
            missing_fields=missing_fields,
            questions=questions,
        )
        async with self._lock:
            self._sessions[session_id] = session
        return session

    async def get_session(self, session_id: str) -> ClarificationSession | None:
        async with self._lock:
            return self._sessions.get(session_id)

    async def delete_session(self, session_id: str) -> None:
        async with self._lock:
            self._sessions.pop(session_id, None)


clarification_store = ClarificationSessionStore()
