"""Estimate service — business logic for estimate CRUD and dashboard.

Wraps EstimateRepository and handles ownership validation, UUID parsing,
and aggregation logic that would otherwise pollute the controller layer.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from infrastructure.data_layer.database.repositories.estimate_repository import (
    EstimateRepository,
)


class EstimateService:
    """Business logic for estimate management and dashboard aggregation."""

    def __init__(self, db: Session) -> None:
        self._repo = EstimateRepository(db)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_uuid(value: str, label: str = "ID") -> uuid.UUID:
        try:
            return uuid.UUID(value)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid {label}: {value!r}",
            )

    def _require_estimate(self, estimate_id: str, user_id: str):
        """Fetch estimate and enforce ownership, raising 404/403 as appropriate."""
        eid = self._parse_uuid(estimate_id, "estimate ID")
        uid = self._parse_uuid(user_id, "user ID")

        est = self._repo.find_by_id(eid)
        if not est:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Estimate not found."
            )
        if str(est.user_id) != str(uid):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied."
            )
        return est

    @staticmethod
    def _to_list_item(est) -> dict:
        pi = est.project_info or {}
        params = pi.get("parameters") or {}
        result = est.result or {}
        floorplan = result.get("floorplan") or {}
        costs = result.get("costs") or {}
        return {
            "id": str(est.id),
            "project_name": est.project_name,
            "status": est.status,
            "confidence": est.confidence,
            "grand_total": est.grand_total,
            "item_count": est.item_count,
            "created_at": est.created_at,
            "updated_at": est.updated_at,
            "building_type": pi.get("building_type"),
            "floors": pi.get("floors"),
            "built_up_area": params.get("built_up_area"),
            "floorplan_accepted": floorplan.get("accepted"),
            "external_works_total": costs.get("external_works_total"),
            # Lifecycle fields for list view
            "progress": est.progress,
            "error_message": est.error_message,
            "cancelled_at": est.cancelled_at,
            "regenerated_from_estimate_id": (
                str(est.regenerated_from_estimate_id)
                if est.regenerated_from_estimate_id else None
            ),
        }

    # ── Business operations ───────────────────────────────────────────────────

    def list_estimates(self, user_id: str, page: int = 1, page_size: int = 20) -> dict:
        uid = self._parse_uuid(user_id, "user ID")
        rows, total = self._repo.find_by_user_paginated(uid, page, page_size)
        return {
            "estimates": [self._to_list_item(r) for r in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get_estimate(self, estimate_id: str, user_id: str) -> dict:
        est = self._require_estimate(estimate_id, user_id)
        return {
            "id": str(est.id),
            "project_name": est.project_name,
            "notes": est.notes,
            "status": est.status,
            "project_info": est.project_info,
            "result": est.result,
            "confidence": est.confidence,
            "grand_total": est.grand_total,
            "item_count": est.item_count,
            "created_at": est.created_at,
            "updated_at": est.updated_at,
            # Lifecycle fields
            "progress": est.progress,
            "error_message": est.error_message,
            "cancelled_at": est.cancelled_at,
            "regenerated_from_estimate_id": (
                str(est.regenerated_from_estimate_id)
                if est.regenerated_from_estimate_id else None
            ),
            "wizard_payload": est.wizard_payload,
        }

    def patch_estimate(
        self,
        estimate_id: str,
        user_id: str,
        project_name: str | None = None,
        notes: str | None = None,
    ) -> dict:
        est = self._require_estimate(estimate_id, user_id)
        updated = self._repo.patch(est, project_name=project_name, notes=notes)
        return {
            "id": str(updated.id),
            "project_name": updated.project_name,
            "notes": updated.notes,
        }

    def delete_estimate(self, estimate_id: str, user_id: str) -> dict:
        est = self._require_estimate(estimate_id, user_id)
        self._repo.soft_delete(est)
        return {"message": "Estimate deleted."}

    def duplicate_estimate(self, estimate_id: str, user_id: str) -> dict:
        est = self._require_estimate(estimate_id, user_id)
        uid = self._parse_uuid(user_id, "user ID")
        new_est = self._repo.duplicate(est, uid)
        return {
            "id": str(new_est.id),
            "project_name": new_est.project_name,
            "status": new_est.status,
        }

    def cancel_estimate(self, estimate_id: str, user_id: str) -> dict:
        """Signal a running estimate to stop and mark it as cancelled in DB."""
        from app.api.state.run_registry import run_registry

        est = self._require_estimate(estimate_id, user_id)

        if est.status != "in_progress":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Estimate is not in progress (current status: {est.status}).",
            )

        # Signal the background runner — DB update will happen in the runner's
        # finally block, but we also update here as a fallback if the runner has
        # already exited.
        signalled = run_registry.signal_cancel(estimate_id)
        if not signalled:
            # Runner already finished — just update the DB directly.
            updated = self._repo.mark_cancelled(est)
        else:
            updated = est  # DB will be updated by the runner

        return {
            "id": str(updated.id),
            "status": updated.status,
            "cancelled_at": updated.cancelled_at,
        }

    async def regenerate_estimate(self, estimate_id: str, user_id: str) -> dict:
        """Create a new estimate from the same wizard payload and start the pipeline."""
        import asyncio
        import threading

        from app.api.services.form_service import FormService
        from app.api.state.run_registry import run_registry
        from app.api.state.session import process_store

        est = self._require_estimate(estimate_id, user_id)

        if not est.wizard_payload:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cannot regenerate: original estimate has no stored wizard payload.",
            )

        uid = self._parse_uuid(user_id, "user ID")
        # Attempt count: count existing regenerations to produce a human title.
        new_name = f"Re-run of {est.project_name or 'Unnamed'}"

        new_est = self._repo.create_regenerated(est, uid, new_name)
        new_id = str(new_est.id)

        project_info = new_est.project_info or {}
        floorplan_urls: list[str] = new_est.wizard_payload.get("floorplan_urls") or []

        cancel_event = threading.Event()

        session = await process_store.create_session(
            description=new_name,
            floorplan_urls=floorplan_urls,
            project_info=project_info,
            session_type="form",
        )
        task = asyncio.create_task(
            FormService.run_pipeline_and_complete(
                session,
                project_info,
                floorplan_urls,
                new_id,
                cancel_event=cancel_event,
            )
        )
        run_registry.register(new_id, task, cancel_event, session.session_id)
        session_id = session.session_id

        return {
            "id": new_id,
            "status": "in_progress",
            "project_name": new_name,
            "created_at": new_est.created_at,
            "regenerated_from_estimate_id": estimate_id,
            "session_id": session_id,
        }

    def get_dashboard_summary(self, user_id: str) -> dict:
        uid = self._parse_uuid(user_id, "user ID")
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        total = self._repo.count_by_user(uid)
        this_month = self._repo.count_since(uid, month_start)

        all_rows = self._repo.find_all_by_user(uid)
        completed_rows = [r for r in all_rows if r.status == "completed" and r.confidence is not None]
        conf_values = [r.confidence for r in completed_rows]
        avg_confidence = round(sum(conf_values) / len(conf_values), 4) if conf_values else None

        total_values = [r.grand_total for r in all_rows if r.grand_total is not None]
        total_value = round(sum(total_values), 2) if total_values else 0.0

        return {
            "total_estimates": total,
            "estimates_this_month": this_month,
            "average_confidence": avg_confidence,
            "total_estimated_value": total_value,
        }
