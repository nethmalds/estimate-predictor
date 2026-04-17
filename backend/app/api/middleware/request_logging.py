import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from core.logging.logger import get_logger


logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:  # noqa: BLE001 - preserve error context
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logger.exception(
                "request_error method=%s path=%s duration_ms=%s",
                request.method,
                request.url.path,
                round(duration_ms, 2),
            )
            raise

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        logger.info(
            "request_done method=%s path=%s status=%s duration_ms=%s",
            request.method,
            request.url.path,
            response.status_code,
            round(duration_ms, 2),
        )
        return response
