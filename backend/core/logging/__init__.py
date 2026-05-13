"""Structured JSON logging setup.

Call configure_logging() once at application startup. Every log record will
include a ``request_id`` field injected from the X-Request-ID context var so
all messages within a request lifecycle share a common correlation ID.
"""
from __future__ import annotations

import logging
import sys

from pythonjsonlogger import jsonlogger

from app.api.middleware.request_id import REQUEST_ID_CTX


class _RequestIDFilter(logging.Filter):
    """Inject request_id into every LogRecord from the context var."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = REQUEST_ID_CTX.get("-")  # type: ignore[attr-defined]
        return True


def configure_logging(level: str = "INFO") -> None:
    """Replace the root handler with a single JSON stream handler to stdout."""
    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
        rename_fields={"asctime": "ts", "levelname": "level", "name": "logger"},
    )
    handler.setFormatter(formatter)
    handler.addFilter(_RequestIDFilter())

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers.clear()
    root.addHandler(handler)

    # Suppress noisy third-party loggers
    for noisy in ("uvicorn.access", "chromadb", "sentence_transformers", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
