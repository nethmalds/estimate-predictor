"""Form service — pipeline orchestration extracted from form_controller.

Provides the async pipeline runner, SSE progress callback factory,
and DB result persistence helpers — all previously embedded in the controller.
"""
from __future__ import annotations

import asyncio
import logging
import threading
import uuid

from sqlalchemy.orm import Session

from application.pipelines.estimation_pipeline import (
    run_estimation_pipeline_from_project_info,
    PipelineCancelledError,
)
from app.api.state.run_registry import run_registry
from infrastructure.data_layer.database.models.estimate import Estimate
from infrastructure.data_layer.database.session import SessionLocal

logger = logging.getLogger(__name__)


class FormService:
    """Orchestrates the estimation pipeline and persists results."""

    # ── Progress callback ────────────────────────────────────────────────────

    @staticmethod
    def build_progress_callback(
        session,
        loop: asyncio.AbstractEventLoop,
        estimate_id: str,
    ):
        """Return a thread-safe callback that pushes progress events and persists snapshots."""
        # Track cumulative progress so we can persist the full snapshot each call.
        completed_steps: list[dict] = []

        def _progress(step: str, status: str, data: dict | None) -> None:
            step_entry = {"step": step, "status": status, **(data or {})}
            completed_steps.append(step_entry)

            event = {
                "event": "progress",
                "data": {"step": step, "status": status, **(data or {})},
            }
            try:
                asyncio.run_coroutine_threadsafe(session.queue.put(event), loop)
            except Exception:  # noqa: BLE001
                pass

            # Persist snapshot to DB (best-effort, same thread since we're in a worker thread).
            try:
                db = SessionLocal()
                try:
                    est = db.query(Estimate).filter(
                        Estimate.id == uuid.UUID(estimate_id)
                    ).first()
                    if est:
                        est.progress = {"steps": list(completed_steps)}
                        db.commit()
                finally:
                    db.close()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not persist progress snapshot: %s", exc)

        return _progress

    # ── Pipeline runner ──────────────────────────────────────────────────────

    @staticmethod
    async def run_pipeline_and_complete(
        session,
        project_info: dict,
        floorplan_urls: list[str],
        estimate_id: str,
        cancel_event: threading.Event | None = None,
    ) -> None:
        """Run the estimation pipeline in a thread and push the SSE completion event."""
        try:
            loop = asyncio.get_running_loop()
            result = await asyncio.to_thread(
                run_estimation_pipeline_from_project_info,
                project_info,
                floorplan_urls=floorplan_urls,
                progress_callback=FormService.build_progress_callback(session, loop, estimate_id),
                cancel_event=cancel_event,
            )
            await asyncio.to_thread(
                FormService.persist_estimate_result, estimate_id, result
            )
            completed_data = dict(result) if isinstance(result, dict) else {}
            completed_data["estimate_id"] = estimate_id
            await session.queue.put({"event": "completed", "data": completed_data})
        except PipelineCancelledError:
            await asyncio.to_thread(FormService.mark_estimate_cancelled, estimate_id)
            await session.queue.put({"event": "cancelled", "data": {"estimate_id": estimate_id}})
        except Exception as exc:  # noqa: BLE001
            await asyncio.to_thread(
                FormService.mark_estimate_failed, estimate_id, str(exc)
            )
            await session.queue.put({"event": "error", "data": {"message": str(exc)}})
        finally:
            run_registry.deregister(estimate_id)

    # ── DB persistence (called in threads) ───────────────────────────────────

    @staticmethod
    def persist_estimate_result(estimate_id: str, result: dict) -> None:
        """Update the Estimate record with pipeline result (runs in a thread)."""
        costs = result.get("costs") or {}
        confidence_data = result.get("confidence") or {}
        boq_items = result.get("boq_items") or []

        try:
            db = SessionLocal()
            try:
                est = db.query(Estimate).filter(
                    Estimate.id == uuid.UUID(estimate_id)
                ).first()
                if est:
                    est.status = "completed"
                    est.result = result
                    est.confidence = confidence_data.get("score")
                    est.grand_total = costs.get("total")
                    est.item_count = len(boq_items) if isinstance(boq_items, list) else None
                    db.commit()
            finally:
                db.close()
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to persist estimate result: %s", exc)

    @staticmethod
    def mark_estimate_failed(estimate_id: str, error_message: str = "") -> None:
        """Mark the Estimate record as failed (runs in a thread)."""
        try:
            db = SessionLocal()
            try:
                est = db.query(Estimate).filter(
                    Estimate.id == uuid.UUID(estimate_id)
                ).first()
                if est:
                    est.status = "failed"
                    est.error_message = error_message or None
                    db.commit()
            finally:
                db.close()
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to mark estimate failed: %s", exc)

    @staticmethod
    def mark_estimate_cancelled(estimate_id: str) -> None:
        """Mark the Estimate record as cancelled (runs in a thread)."""
        from datetime import datetime, timezone

        try:
            db = SessionLocal()
            try:
                est = db.query(Estimate).filter(
                    Estimate.id == uuid.UUID(estimate_id)
                ).first()
                if est:
                    est.status = "cancelled"
                    est.cancelled_at = datetime.now(timezone.utc)
                    db.commit()
            finally:
                db.close()
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to mark estimate cancelled: %s", exc)

