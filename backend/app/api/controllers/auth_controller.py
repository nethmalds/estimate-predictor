"""Authentication controller — thin HTTP adapter.

All business logic has been moved to app.api.services.auth_service.AuthService.
This module's sole responsibility is: parse the HTTP request → call the service
→ return the HTTP response.
"""
from __future__ import annotations

from fastapi import Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.middleware.rate_limit import limiter, _dev_limit
from app.api.schemas.auth_schemas import (
    ForgotPasswordRequest,
    ResetPasswordRequest,
    UserLoginRequest,
    UserRegisterRequest,
    # NEW: H11
    ResendVerificationRequest,
)
from app.api.services.auth_service import AuthService
from infrastructure.data_layer.database.session import get_db_session


@limiter.limit(_dev_limit("5/minute"))
async def register_user(
    request: Request,
    body: UserRegisterRequest,
    db: Session = Depends(get_db_session),
) -> dict:
    """POST /api/users/register"""
    return AuthService(db).register(
        name=body.name,
        email=body.email,
        password=body.password,
        role=body.role,
    )


@limiter.limit(_dev_limit("10/minute"))
async def login_user(
    request: Request,
    body: UserLoginRequest,
    db: Session = Depends(get_db_session),
) -> dict:
    """POST /api/auth/login"""
    return AuthService(db).login(email=body.email, password=body.password)


@limiter.limit(_dev_limit("5/minute"))
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    db: Session = Depends(get_db_session),
) -> dict:
    """POST /api/auth/forgot-password"""
    return AuthService(db).request_password_reset(email=body.email)


@limiter.limit(_dev_limit("10/minute"))
async def reset_password(
    request: Request,
    body: ResetPasswordRequest,
    db: Session = Depends(get_db_session),
) -> dict:
    """POST /api/auth/reset-password"""
    return AuthService(db).reset_password(
        token=body.token,
        new_password=body.new_password,
    )


# NEW: H11 — email verification route handlers
async def verify_email(
    token: str = Query(..., description="Single-use verification token from the email link"),
    db: Session = Depends(get_db_session),
) -> dict:
    """GET /api/auth/verify-email?token=..."""
    return AuthService(db).verify_email(token)


@limiter.limit(_dev_limit("3/hour"))
async def resend_verification(
    request: Request,
    body: ResendVerificationRequest,
    db: Session = Depends(get_db_session),
) -> dict:
    """POST /api/auth/resend-verification"""
    return AuthService(db).resend_verification_email(email=body.email)
