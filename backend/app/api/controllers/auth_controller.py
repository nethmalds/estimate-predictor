"""Authentication controller — thin HTTP adapter.

All business logic has been moved to app.api.services.auth_service.AuthService.
This module's sole responsibility is: parse the HTTP request → call the service
→ return the HTTP response.
"""
from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.schemas.auth_schemas import (
    ForgotPasswordRequest,
    ResetPasswordRequest,
    UserLoginRequest,
    UserRegisterRequest,
)
from app.api.services.auth_service import AuthService
from infrastructure.data_layer.database.session import get_db_session


async def register_user(
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


async def login_user(
    body: UserLoginRequest,
    db: Session = Depends(get_db_session),
) -> dict:
    """POST /api/auth/login"""
    return AuthService(db).login(email=body.email, password=body.password)


async def forgot_password(
    body: ForgotPasswordRequest,
    db: Session = Depends(get_db_session),
) -> dict:
    """POST /api/auth/forgot-password"""
    return AuthService(db).request_password_reset(email=body.email)


async def reset_password(
    body: ResetPasswordRequest,
    db: Session = Depends(get_db_session),
) -> dict:
    """POST /api/auth/reset-password"""
    return AuthService(db).reset_password(
        token=body.token,
        new_password=body.new_password,
    )
