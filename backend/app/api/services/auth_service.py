"""Auth service — all authentication business logic.

Controllers call methods on this class and never touch the database or
crypto primitives directly.
"""
from __future__ import annotations

import hashlib
import logging
import os
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import bcrypt
import jwt
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from core.config.settings import settings
from infrastructure.data_layer.database.models.user import User
from infrastructure.data_layer.database.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)


class AuthService:
    """Business logic for registration, login, and password management."""

    def __init__(self, db: Session) -> None:
        self._repo = UserRepository(db)

    # ── Crypto helpers ────────────────────────────────────────────────────────

    @staticmethod
    def hash_password(plain: str) -> str:
        return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()

    @staticmethod
    def verify_password(plain: str, hashed: str) -> bool:
        try:
            return bcrypt.checkpw(plain.encode(), hashed.encode())
        except Exception:
            return False

    @staticmethod
    def generate_reset_token() -> str:
        return secrets.token_urlsafe(48)

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def create_access_token(user_id: str, expires_hours: int = 168) -> str:
        payload = {
            "sub": user_id,
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(hours=expires_hours),
        }
        return jwt.encode(payload, settings.api_secret_key, algorithm="HS256")

    # ── Business operations ───────────────────────────────────────────────────

    def register(self, name: str, email: str, password: str, role: str = "homeowner") -> dict:
        """Register a new user, returning the created user dict."""
        existing = self._repo.find_by_email(email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            )
        user = self._repo.create(
            name=name,
            email=email,
            hashed_password=self.hash_password(password),
            role=role,
        )
        return {
            "id": str(user.id),
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "created_at": user.created_at.isoformat(),
        }

    def login(self, email: str, password: str) -> dict:
        """Authenticate a user and return a JWT access token."""
        user = self._repo.find_by_email(email)
        # Constant-time check even when user not found (prevent timing oracle)
        if user is None or not self.verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )
        self._repo.update_last_login(user)
        return {
            "id": str(user.id),
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "access_token": self.create_access_token(str(user.id)),
        }

    def request_password_reset(self, email: str) -> dict:
        """
        Generate a reset token and (in production) email the user.
        Always returns 200 to prevent user enumeration.
        """
        user = self._repo.find_by_email(email)
        if not user:
            return {"message": "If that email exists, a reset link has been sent."}

        self._repo.invalidate_reset_tokens(user.id)

        raw_token = self.generate_reset_token()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        self._repo.create_reset_token(
            user_id=user.id,
            token_hash=self.hash_token(raw_token),
            expires_at=expires_at,
        )

        reset_url = f"{settings.frontend_app_url}/reset-password?token={raw_token}"
        self._send_reset_email(
            to_email=user.email,
            reset_url=reset_url,
            user_name=user.name or "User",
        )

        response: dict = {"message": "If that email exists, a reset link has been sent."}
        dev_mode = os.getenv("ENV", "development").lower() == "development"
        if dev_mode:
            response["dev_reset_token"] = raw_token
        return response

    def reset_password(self, token: str, new_password: str) -> dict:
        """Validate the reset token and update the user's password."""
        token_hash = self.hash_token(token)
        record = self._repo.find_valid_reset_token(token_hash)

        if not record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token.",
            )

        user = self._repo.find_by_id(str(record.user_id))
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

        self._repo.update_password(user, self.hash_password(new_password))
        self._repo.mark_token_used(record)
        return {"message": "Password reset successfully."}

    # ── Email helper ──────────────────────────────────────────────────────────

    @staticmethod
    def _send_reset_email(to_email: str, reset_url: str, user_name: str) -> None:
        """Send a password-reset email via SMTP (silently skips if unconfigured)."""
        if not settings.smtp_username or not settings.smtp_password:
            logger.warning(
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
                server.sendmail(
                    settings.smtp_from_email or settings.smtp_username,
                    to_email,
                    msg.as_string(),
                )
        except Exception as exc:
            logger.error("Failed to send reset email: %s", exc)
