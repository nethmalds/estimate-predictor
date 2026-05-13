"""Structured audit log middleware.

Emits a single JSON log line for every mutating request (POST / PATCH / DELETE)
and for security-sensitive GET endpoints.  Auth events (login success/failure,
registration, password-reset) are additionally logged by AuthService directly
so they include user-level context.
"""
from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.api.middleware.request_id import REQUEST_ID_CTX

_AUDIT_METHODS = {"POST", "PATCH", "DELETE", "PUT"}
_SKIP_PATHS = {"/health", "/healthz", "/readyz", "/"}

audit_logger = logging.getLogger("audit")


class AuditLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method not in _AUDIT_METHODS or request.url.path in _SKIP_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        response: Response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 1)

        audit_logger.info(
            "http_mutation",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
                "request_id": REQUEST_ID_CTX.get("-"),
                "client_ip": _client_ip(request),
            },
        )
        return response


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "-"
