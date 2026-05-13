"""User repository — abstracts all database operations for User and PasswordResetToken.

Controllers/services must interact with the User model only through this class,
keeping raw SQLAlchemy queries out of business logic.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from infrastructure.data_layer.database.models.user import PasswordResetToken, User


class UserRepository:
    """Data-access layer for the User and PasswordResetToken models."""

    def __init__(self, db: Session) -> None:
        self._db = db

    # ── User queries ─────────────────────────────────────────────────────────

    def find_by_email(self, email: str) -> Optional[User]:
        return self._db.query(User).filter(User.email == email.lower()).first()

    def find_by_id(self, user_id: str) -> Optional[User]:
        import uuid
        try:
            uid = uuid.UUID(user_id)
        except ValueError:
            return None
        return self._db.query(User).filter(User.id == uid).first()

    def create(
        self,
        name: str,
        email: str,
        hashed_password: str,
        role: str = "homeowner",
    ) -> User:
        user = User(
            name=name,
            email=email.lower(),
            hashed_password=hashed_password,
            role=role,
        )
        self._db.add(user)
        self._db.commit()
        self._db.refresh(user)
        return user

    def update_last_login(self, user: User) -> None:
        user.last_login_at = datetime.now(timezone.utc)
        self._db.commit()

    def update_password(self, user: User, hashed_password: str) -> None:
        user.hashed_password = hashed_password
        self._db.commit()

    # ── Password reset token queries ─────────────────────────────────────────

    def invalidate_reset_tokens(self, user_id) -> None:
        """Invalidate all unused tokens for the user before issuing a new one."""
        self._db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.used == False,  # noqa: E712
        ).delete()
        self._db.flush()

    def create_reset_token(self, user_id, token_hash: str, expires_at: datetime) -> PasswordResetToken:
        record = PasswordResetToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self._db.add(record)
        self._db.commit()
        return record

    def find_valid_reset_token(self, token_hash: str) -> Optional[PasswordResetToken]:
        now = datetime.now(timezone.utc)
        return (
            self._db.query(PasswordResetToken)
            .filter(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.used == False,  # noqa: E712
                PasswordResetToken.expires_at > now,
            )
            .first()
        )

    def mark_token_used(self, record: PasswordResetToken) -> None:
        record.used = True
        self._db.commit()

    # NEW: H11 — email verification helpers ──────────────────────────────────

    def find_by_verification_token(self, token_hash: str) -> Optional[User]:
        """Return the user whose verification_token matches the given hash."""
        return (
            self._db.query(User)
            .filter(User.verification_token == token_hash)
            .first()
        )

    def set_verification_token(
        self,
        user: User,
        token_hash: str | None,
        sent_at: datetime | None,
    ) -> None:
        user.verification_token = token_hash
        user.verification_sent_at = sent_at
        self._db.commit()

    def mark_verified(self, user: User) -> None:
        user.is_verified = True
        user.verification_token = None
        user.verification_sent_at = None
        self._db.commit()
