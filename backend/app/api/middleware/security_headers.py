"""ASGI middleware that injects security headers on every response."""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
    # API-only: tight CSP — no HTML served from this origin
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}

# Only sent over HTTPS; Caddy handles TLS termination in production.
_HSTS = "max-age=31536000; includeSubDomains"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, is_production: bool = False) -> None:
        super().__init__(app)
        self._is_production = is_production

    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)
        for name, value in _HEADERS.items():
            response.headers[name] = value
        if self._is_production:
            response.headers["Strict-Transport-Security"] = _HSTS
        return response
