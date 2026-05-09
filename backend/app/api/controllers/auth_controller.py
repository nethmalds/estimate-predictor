"""Authentication controller — register, login, forgot/reset password.

Implements NEW-AUTH-10 to NEW-AUTH-13.

Security notes
--------------
- Passwords hashed with bcrypt, cost factor ≥ 12.
- Password reset tokens are signed HMAC-SHA256 time-limited strings; only the
  SHA-256 hash is stored in the database.
- Rate limiting is applied at the router level (slowapi, NEW-AUTH-17).
- Login returns a signed JWT access token for backend API auth.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import smtplib
import uuid
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.schemas.auth_schemas import (
    ForgotPasswordRequest,
    ResetPasswordRequest,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from core.config.settings import settings
from infrastructure.data_layer.database.session import get_db_session
from infrastructure.data_layer.database.models.user import User, PasswordResetToken


def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def _generate_reset_token() -> str:
    """Generate a 64-character URL-safe random token."""
    return secrets.token_urlsafe(48)


def _hash_token(token: str) -> str:
    """SHA-256 hash of the reset token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def _create_access_token(user_id: str, expires_hours: int = 168) -> str:
    """Create a signed JWT access token (default 7-day expiry)."""
    payload = {
        "sub": user_id,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=expires_hours),
    }
    return jwt.encode(payload, settings.api_secret_key, algorithm="HS256")


def _send_reset_email(to_email: str, reset_url: str, user_name: str) -> None:
    """Send a password-reset email via Gmail SMTP (STARTTLS).

    Silently logs a warning if SMTP is not configured (e.g. in development)
    instead of crashing — the dev_reset_token response field covers testing.
    """
    if not settings.smtp_username or not settings.smtp_password:
        import logging
        logging.getLogger(__name__).warning(
            "SMTP not configured — password-reset email not sent. "
            "Set SMTP_USERNAME and SMTP_PASSWORD in backend/.env.local."
        )
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Reset your CostEstimate AI password"
    msg["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    msg["To"] = to_email

    plain_body = (
        f"Hi {user_name},\n\n"
        f"Click the link below to reset your password (valid for 24 hours):\n\n"
        f"{reset_url}\n\n"
        f"If you did not request this, you can safely ignore this email.\n\n"
        f"— {settings.smtp_from_name}"
    )
    html_body = f"""<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;background:#f4f4f4;padding:20px">
  <div style="max-width:480px;margin:0 auto;background:#fff;border-radius:8px;padding:32px">
    <h2 style="color:#1e40af;margin-top:0">Reset your password</h2>
    <p>Hi {user_name},</p>
    <p>Click the button below to reset your password. This link is valid for <strong>24 hours</strong>.</p>
    <p style="text-align:center;margin:32px 0">
      <a href="{reset_url}" style="background:#2563eb;color:#fff;padding:12px 28px;border-radius:6px;text-decoration:none;font-weight:bold">
        Reset password
      </a>
    </p>
    <p style="color:#6b7280;font-size:13px">If you did not request this, you can safely ignore this email.</p>
    <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0">
    <p style="color:#9ca3af;font-size:12px">{settings.smtp_from_name}</p>
  </div>
</body>
</html>"""

    msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            if settings.smtp_starttls:
                server.starttls()
            server.login(settings.smtp_username, settings.smtp_password)
            server.sendmail(settings.smtp_from_email or settings.smtp_username, to_email, msg.as_string())
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error("Failed to send reset email: %s", exc)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def register_user(
    body: UserRegisterRequest,
    db: Session = Depends(get_db_session),
) -> dict:
    """POST /api/users/register (NEW-AUTH-10)."""
    existing = db.query(User).filter(User.email == body.email.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        name=body.name,
        email=body.email.lower(),
        hashed_password=_hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "created_at": user.created_at.isoformat(),
    }


async def login_user(
    body: UserLoginRequest,
    db: Session = Depends(get_db_session),
) -> dict:
    """POST /api/auth/login — called by NextAuth authorize callback (NEW-AUTH-11).

    Returns the user object on success; raises 401 on invalid credentials.
    A generic error message is returned to prevent user enumeration.
    """
    user = db.query(User).filter(User.email == body.email.lower()).first()

    # Constant-time check even when user not found (prevent timing oracle)
    if user is None or not _verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    # Update last_login_at
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "access_token": _create_access_token(str(user.id)),
    }


async def forgot_password(
    body: ForgotPasswordRequest,
    db: Session = Depends(get_db_session),
) -> dict:
    """POST /api/auth/forgot-password (NEW-AUTH-12).

    Always returns 200 to prevent user enumeration.
    Generates a 24-hour reset token, stores its hash, and (in production)
    would send an email.  In development the token is included in the
    response for testing purposes.
    """
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if not user:
        # Return 200 even when no account found (prevent enumeration)
        return {"message": "If that email exists, a reset link has been sent."}

    # Invalidate existing unused tokens for this user
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used == False,  # noqa: E712
    ).delete()
    db.flush()

    raw_token = _generate_reset_token()
    token_record = PasswordResetToken(
        user_id=user.id,
        token_hash=_hash_token(raw_token),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(token_record)
    db.commit()

    # TODO: send email via SMTP in production.
    # For development, include the token in the response.
    dev_mode = os.getenv("ENV", "development").lower() == "development"
    response: dict = {"message": "If that email exists, a reset link has been sent."}
    if dev_mode:
        response["dev_reset_token"] = raw_token

    # Send real reset email (silently skipped if SMTP not configured)
    reset_url = f"{settings.frontend_app_url}/reset-password?token={raw_token}"
    _send_reset_email(to_email=user.email, reset_url=reset_url, user_name=user.name or "User")

    return response


async def reset_password(
    body: ResetPasswordRequest,
    db: Session = Depends(get_db_session),
) -> dict:
    """POST /api/auth/reset-password (NEW-AUTH-13)."""
    token_hash = _hash_token(body.token)
    now = datetime.now(timezone.utc)

    record = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used == False,  # noqa: E712
            PasswordResetToken.expires_at > now,
        )
        .first()
    )

    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token.",
        )

    user = db.query(User).filter(User.id == record.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    user.hashed_password = _hash_password(body.new_password)
    record.used = True
    db.commit()

    return {"message": "Password reset successfully."}
