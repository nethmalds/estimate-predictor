import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from core.logging.logger import ensure_logging, get_logger
logger = get_logger(__name__)


@dataclass
class ProcessSession:
    session_id: str
    created_at: float
    description: str
    floorplan_image_url: str | None
    session_type: str = "clarification"
    project_info: dict | None = None
    missing_fields: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    answers: dict[str, Any] = field(default_factory=dict)
    current_index: int = 0
    awaiting_confirmation: bool = False
    confirmed_project_info: dict | None = None
    queue: asyncio.Queue[dict[str, Any]] = field(default_factory=asyncio.Queue)


_SESSION_TTL_SECONDS = 3600  # 1 hour


class ProcessSessionStore:
    def __init__(self) -> None:
        ensure_logging()
        self._sessions: dict[str, ProcessSession] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task | None = None

    def start_cleanup(self) -> None:
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self) -> None:
        while True:
            await asyncio.sleep(600)  # run every 10 minutes
            await self._evict_expired()

    async def _evict_expired(self) -> None:
        cutoff = time.time() - _SESSION_TTL_SECONDS
        async with self._lock:
            expired = [sid for sid, s in self._sessions.items() if s.created_at < cutoff]
            for sid in expired:
                del self._sessions[sid]
        for sid in expired:
            logger.info("session_expired session_id=%s", sid)

    async def create_session(
        self,
        description: str,
        floorplan_image_url: str | None,
        project_info: dict | None = None,
        missing_fields: list[str] | None = None,
        questions: list[str] | None = None,
        session_type: str = "clarification",
    ) -> ProcessSession:
        ensure_logging()
        session_id = uuid.uuid4().hex
        session = ProcessSession(
            session_id=session_id,
            created_at=time.time(),
            description=description,
            floorplan_image_url=floorplan_image_url,
            session_type=session_type,
            project_info=project_info,
            missing_fields=missing_fields or [],
            questions=questions or [],
        )
        async with self._lock:
            self._sessions[session_id] = session
        logger.info(
            "session_start session_id=%s type=%s",
            session.session_id,
            session.session_type,
        )
        return session

    async def get_session(self, session_id: str) -> ProcessSession | None:
        async with self._lock:
            session = self._sessions.get(session_id)
        if session:
            logger.info(
                "session_access session_id=%s type=%s",
                session.session_id,
                session.session_type,
            )
        else:
            logger.info("session_missing session_id=%s", session_id)
        return session

    async def delete_session(self, session_id: str) -> None:
        async with self._lock:
            session = self._sessions.pop(session_id, None)
        if session:
            logger.info(
                "session_end session_id=%s type=%s",
                session.session_id,
                session.session_type,
            )


process_store = ProcessSessionStore()
