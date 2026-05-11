"""In-memory registry of active estimation pipeline runs.

Keyed by estimate_id (str).  Each entry stores the asyncio Task and a
threading.Event that can be signalled to request cooperative cancellation.
"""
from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field


@dataclass
class RunEntry:
    task: asyncio.Task
    cancel_event: threading.Event
    session_id: str


class RunRegistry:
    """Thread-safe registry of in-flight estimation runs."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._runs: dict[str, RunEntry] = {}

    def register(
        self,
        estimate_id: str,
        task: asyncio.Task,
        cancel_event: threading.Event,
        session_id: str,
    ) -> None:
        with self._lock:
            self._runs[estimate_id] = RunEntry(
                task=task,
                cancel_event=cancel_event,
                session_id=session_id,
            )

    def deregister(self, estimate_id: str) -> None:
        with self._lock:
            self._runs.pop(estimate_id, None)

    def get(self, estimate_id: str) -> RunEntry | None:
        with self._lock:
            return self._runs.get(estimate_id)

    def signal_cancel(self, estimate_id: str) -> bool:
        """Signal cancellation for a run.  Returns True if the run existed."""
        with self._lock:
            entry = self._runs.get(estimate_id)
            if entry is None:
                return False
            entry.cancel_event.set()
            return True

    def is_active(self, estimate_id: str) -> bool:
        with self._lock:
            return estimate_id in self._runs


# Module-level singleton used by both form_controller and estimate_service.
run_registry = RunRegistry()
