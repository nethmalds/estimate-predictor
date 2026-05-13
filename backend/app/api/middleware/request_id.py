"""X-Request-ID middleware.

Reads the incoming X-Request-ID header; if absent, generates a UUID4.
Stores the value in a context variable (REQUEST_ID_CTX) so log formatters
can inject it automatically, and echoes it back in the response header.
"""
from __future__ import annotations

import contextvars
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

HEADER_NAME = "X-Request-ID"

# Module-level context var — imported by core/logging/__init__.py
REQUEST_ID_CTX: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get(HEADER_NAME) or str(uuid.uuid4())
        REQUEST_ID_CTX.set(request_id)
        request.state.request_id = request_id

        response: Response = await call_next(request)
        response.headers[HEADER_NAME] = request_id
        return response
