"""Process session store — hybrid in-process + Redis.

In-process dict holds asyncio.Queue objects (not serialisable).
Redis holds serialisable session metadata with TTL.

Fallback: if REDIS_URL is absent or the connection fails, the store
operates purely in-process (same behaviour as before this change).
"""
import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from infrastructure.cache.redis_client import get_redis

logger = logging.getLogger(__name__)

_SESSION_TTL_SECONDS = 3600  # 1 hour
_REDIS_KEY_PREFIX = "session:"


@dataclass
class ProcessSession:
    session_id: str
    created_at: float
    description: str
    floorplan_urls: list[str]
    session_type: str = "clarification"
    project_info: dict | None = None
    missing_fields: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    answers: dict[str, Any] = field(default_factory=dict)
    current_index: int = 0
    awaiting_confirmation: bool = False
    confirmed_project_info: dict | None = None
    queue: asyncio.Queue[dict[str, Any]] = field(default_factory=asyncio.Queue)


def _to_dict(s: ProcessSession) -> dict:
    return {
        "session_id": s.session_id,
        "created_at": s.created_at,
        "description": s.description,
        "floorplan_urls": s.floorplan_urls,
        "session_type": s.session_type,
        "project_info": s.project_info,
        "missing_fields": s.missing_fields,
        "questions": s.questions,
        "answers": s.answers,
        "current_index": s.current_index,
        "awaiting_confirmation": s.awaiting_confirmation,
        "confirmed_project_info": s.confirmed_project_info,
    }


def _from_dict(data: dict, queue: asyncio.Queue) -> ProcessSession:
    return ProcessSession(
        session_id=data["session_id"],
        created_at=data["created_at"],
        description=data["description"],
        floorplan_urls=data["floorplan_urls"],
        session_type=data.get("session_type", "clarification"),
        project_info=data.get("project_info"),
        missing_fields=data.get("missing_fields", []),
        questions=data.get("questions", []),
        answers=data.get("answers", {}),
        current_index=data.get("current_index", 0),
        awaiting_confirmation=data.get("awaiting_confirmation", False),
        confirmed_project_info=data.get("confirmed_project_info"),
        queue=queue,
    )


class ProcessSessionStore:
    """Session store backed by Redis (when available) with an in-process queue registry.

    Redis stores serialisable metadata with a TTL.
    The asyncio.Queue for each session lives in _queues (in-process only).
    On worker restart all queues are gone, so any Redis entry whose queue is
    missing is treated as expired and cleaned up immediately.
    """

    def __init__(self) -> None:
        # In-process fallback (used when Redis is absent)
        self._sessions: dict[str, ProcessSession] = {}
        # Queue registry for the Redis-backed path (queue is not serialisable)
        self._queues: dict[str, asyncio.Queue] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task | None = None

    def start_cleanup(self) -> None:
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self) -> None:
        while True:
            await asyncio.sleep(600)
            await self._evict_expired()

    async def _evict_expired(self) -> None:
        cutoff = time.time() - _SESSION_TTL_SECONDS
        async with self._lock:
            expired = [sid for sid, s in self._sessions.items() if s.created_at < cutoff]
            for sid in expired:
                del self._sessions[sid]
            # Also prune orphaned queues
            stale_queues = [sid for sid in self._queues if sid not in self._sessions]
            for sid in stale_queues:
                del self._queues[sid]

    async def create_session(
        self,
        description: str,
        floorplan_urls: list[str] | None = None,
        project_info: dict | None = None,
        missing_fields: list[str] | None = None,
        questions: list[str] | None = None,
        session_type: str = "clarification",
    ) -> ProcessSession:
        session_id = uuid.uuid4().hex
        session = ProcessSession(
            session_id=session_id,
            created_at=time.time(),
            description=description,
            floorplan_urls=floorplan_urls or [],
            session_type=session_type,
            project_info=project_info,
            missing_fields=missing_fields or [],
            questions=questions or [],
        )

        redis = get_redis()
        if redis is not None:
            try:
                await redis.setex(
                    f"{_REDIS_KEY_PREFIX}{session_id}",
                    _SESSION_TTL_SECONDS,
                    json.dumps(_to_dict(session)),
                )
                async with self._lock:
                    self._queues[session_id] = session.queue
            except Exception as exc:
                logger.warning("Redis write failed for session %s: %s", session_id, exc)
                async with self._lock:
                    self._sessions[session_id] = session
        else:
            async with self._lock:
                self._sessions[session_id] = session

        return session

    async def get_session(self, session_id: str) -> ProcessSession | None:
        redis = get_redis()
        if redis is not None:
            try:
                data_str = await redis.get(f"{_REDIS_KEY_PREFIX}{session_id}")
                if data_str is None:
                    return None
                async with self._lock:
                    queue = self._queues.get(session_id)
                if queue is None:
                    # Queue lost (worker restart) — session is dead; clean up
                    await redis.delete(f"{_REDIS_KEY_PREFIX}{session_id}")
                    return None
                return _from_dict(json.loads(data_str), queue)
            except Exception as exc:
                logger.warning("Redis read failed for session %s: %s", session_id, exc)
                # Fall through to in-process fallback

        async with self._lock:
            return self._sessions.get(session_id)

    async def delete_session(self, session_id: str) -> None:
        redis = get_redis()
        if redis is not None:
            try:
                await redis.delete(f"{_REDIS_KEY_PREFIX}{session_id}")
            except Exception as exc:
                logger.warning("Redis delete failed for session %s: %s", session_id, exc)
            async with self._lock:
                self._queues.pop(session_id, None)
        async with self._lock:
            self._sessions.pop(session_id, None)


process_store = ProcessSessionStore()
