from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse




class AppError(Exception):
    def __init__(
        self,
        message: str,
        status_code: int = 400,
        error_code: str = "APP_ERROR",
        details: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}


def _error_payload(
    message: str,
    code: str,
    status_code: int,
    details: dict | list | None = None,
    path: str | None = None,
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
        "status_code": status_code,
        "path": path,
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error_handler(request: Request, exc: AppError):
        payload = _error_payload(
            message=exc.message,
            code=exc.error_code,
            status_code=exc.status_code,
            details=exc.details,
            path=request.url.path,
        )
        return JSONResponse(status_code=exc.status_code, content=payload)

    @app.exception_handler(HTTPException)
    async def _http_error_handler(request: Request, exc: HTTPException):
        payload = _error_payload(
            message=str(exc.detail),
            code="HTTP_ERROR",
            status_code=exc.status_code,
            details={},
            path=request.url.path,
        )
        return JSONResponse(status_code=exc.status_code, content=payload)

    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(request: Request, exc: RequestValidationError):
        payload = _error_payload(
            message="Validation failed",
            code="VALIDATION_ERROR",
            status_code=422,
            details=exc.errors(),
            path=request.url.path,
        )
        return JSONResponse(status_code=422, content=payload)

    @app.exception_handler(Exception)
    async def _unhandled_error_handler(request: Request, exc: Exception):
        payload = _error_payload(
            message="Internal server error",
            code="INTERNAL_ERROR",
            status_code=500,
            details={},
            path=request.url.path,
        )
        return JSONResponse(status_code=500, content=payload)
