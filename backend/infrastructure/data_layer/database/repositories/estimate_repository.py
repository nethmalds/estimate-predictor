"""Estimate repository — abstracts all database operations for the Estimate model.

Provides paginated queries, ownership-enforced lookups, and bulk summary
aggregations for the dashboard.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from infrastructure.data_layer.database.models.estimate import Estimate


class EstimateRepository:
    """Data-access layer for the Estimate model."""

    def __init__(self, db: Session) -> None:
        self._db = db

    # ── Queries ──────────────────────────────────────────────────────────────

    def find_by_user_paginated(
        self,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Estimate], int]:
        """Return (rows, total) for a paginated estimate list."""
        base_q = (
            self._db.query(Estimate)
            .filter(Estimate.user_id == user_id, Estimate.deleted == False)  # noqa: E712
            .order_by(Estimate.created_at.desc())
        )
        total = base_q.count()
        rows = base_q.offset((page - 1) * page_size).limit(page_size).all()
        return rows, total

    def find_by_id(self, estimate_id: uuid.UUID) -> Optional[Estimate]:
        return (
            self._db.query(Estimate)
            .filter(Estimate.id == estimate_id, Estimate.deleted == False)  # noqa: E712
            .first()
        )

    def find_by_id_and_user(
        self, estimate_id: uuid.UUID, user_id: uuid.UUID
    ) -> Optional[Estimate]:
        """Fetch estimate and enforce ownership in a single query."""
        return (
            self._db.query(Estimate)
            .filter(
                Estimate.id == estimate_id,
                Estimate.user_id == user_id,
                Estimate.deleted == False,  # noqa: E712
            )
            .first()
        )

    def find_all_by_user(self, user_id: uuid.UUID) -> list[Estimate]:
        return (
            self._db.query(Estimate)
            .filter(Estimate.user_id == user_id, Estimate.deleted == False)  # noqa: E712
            .all()
        )

    # ── Mutations ────────────────────────────────────────────────────────────

    def create(
        self,
        user_id: uuid.UUID,
        project_name: str,
        status: str = "in_progress",
        project_info: dict | None = None,
        wizard_payload: dict | None = None,
    ) -> Estimate:
        estimate = Estimate(
            user_id=user_id,
            project_name=project_name,
            status=status,
            project_info=project_info,
            wizard_payload=wizard_payload,
        )
        self._db.add(estimate)
        self._db.commit()
        self._db.refresh(estimate)
        return estimate

    def update_progress(self, estimate: Estimate, progress_snapshot: dict) -> None:
        """Persist a live progress snapshot to the estimate row."""
        estimate.progress = progress_snapshot
        self._db.commit()

    def mark_cancelled(self, estimate: Estimate) -> Estimate:
        """Mark an estimate as cancelled and record the timestamp."""
        estimate.status = "cancelled"
        estimate.cancelled_at = datetime.now(timezone.utc)
        self._db.commit()
        self._db.refresh(estimate)
        return estimate

    def create_regenerated(
        self,
        source_estimate: Estimate,
        user_id: uuid.UUID,
        new_name: str,
    ) -> Estimate:
        """Create a new estimate seeded from source_estimate's wizard_payload."""
        new_est = Estimate(
            user_id=user_id,
            project_name=new_name,
            status="in_progress",
            project_info=source_estimate.project_info,
            wizard_payload=source_estimate.wizard_payload,
            regenerated_from_estimate_id=source_estimate.id,
        )
        self._db.add(new_est)
        self._db.commit()
        self._db.refresh(new_est)
        return new_est

    def patch(
        self,
        estimate: Estimate,
        project_name: str | None = None,
        notes: str | None = None,
    ) -> Estimate:
        if project_name is not None:
            estimate.project_name = project_name
        if notes is not None:
            estimate.notes = notes
        self._db.commit()
        self._db.refresh(estimate)
        return estimate

    def soft_delete(self, estimate: Estimate) -> None:
        estimate.deleted = True
        self._db.commit()

    def duplicate(self, estimate: Estimate, user_id: uuid.UUID) -> Estimate:
        new_est = Estimate(
            user_id=user_id,
            project_name=f"Copy of {estimate.project_name or 'Unnamed'}",
            status="in_progress",
            project_info=estimate.project_info,
            wizard_payload=estimate.wizard_payload,
        )
        self._db.add(new_est)
        self._db.commit()
        self._db.refresh(new_est)
        return new_est

    # ── Dashboard aggregations ───────────────────────────────────────────────

    def count_by_user(self, user_id: uuid.UUID) -> int:
        return (
            self._db.query(Estimate)
            .filter(Estimate.user_id == user_id, Estimate.deleted == False)  # noqa: E712
            .count()
        )

    def count_since(self, user_id: uuid.UUID, since: datetime) -> int:
        return (
            self._db.query(Estimate)
            .filter(
                Estimate.user_id == user_id,
                Estimate.deleted == False,  # noqa: E712
                Estimate.created_at >= since,
            )
            .count()
        )
