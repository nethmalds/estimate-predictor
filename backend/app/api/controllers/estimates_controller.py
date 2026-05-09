"""Estimates CRUD controller (NEW-DASH-15).

Provides list, detail, patch, delete, and duplicate endpoints.
All endpoints enforce ownership — users can only access their own estimates.
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.middleware.auth_dependency import get_current_user_id
from app.api.schemas.estimate_schemas import (
    EstimateDetail,
    EstimateListItem,
    EstimateListResponse,
    EstimatePatchRequest,
)
from infrastructure.data_layer.database.models.estimate import Estimate
from infrastructure.data_layer.database.session import get_db_session


def _estimate_to_list_item(est: Estimate) -> dict:
    pi = est.project_info or {}
    params = pi.get("parameters") or {}
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
    }


def _require_estimate(db: Session, estimate_id: str, user_id: str) -> Estimate:
    """Fetch estimate and enforce ownership, raising 404/403 as appropriate."""
    try:
        eid = uuid.UUID(estimate_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estimate not found.")

    est = db.query(Estimate).filter(
        Estimate.id == eid, Estimate.deleted == False  # noqa: E712
    ).first()
    if not est:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estimate not found.")
    if str(est.user_id) != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    return est


# ---------------------------------------------------------------------------
# Handlers (called from router)
# ---------------------------------------------------------------------------

async def list_estimates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
) -> dict:
    """GET /api/estimates — paginated list for the authenticated user."""
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        return {"estimates": [], "total": 0, "page": page, "page_size": page_size}

    base_q = db.query(Estimate).filter(
        Estimate.user_id == uid, Estimate.deleted == False  # noqa: E712
    ).order_by(Estimate.created_at.desc())

    total = base_q.count()
    rows = base_q.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "estimates": [_estimate_to_list_item(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def get_estimate(
    estimate_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
) -> dict:
    """GET /api/estimates/{id} — single estimate detail."""
    est = _require_estimate(db, estimate_id, user_id)
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
    }


async def patch_estimate(
    estimate_id: str,
    body: EstimatePatchRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
) -> dict:
    """PATCH /api/estimates/{id} — update project_name and/or notes."""
    est = _require_estimate(db, estimate_id, user_id)
    if body.project_name is not None:
        est.project_name = body.project_name
    if body.notes is not None:
        est.notes = body.notes
    db.commit()
    db.refresh(est)
    return {"id": str(est.id), "project_name": est.project_name, "notes": est.notes}


async def delete_estimate(
    estimate_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
) -> dict:
    """DELETE /api/estimates/{id} — soft-delete."""
    est = _require_estimate(db, estimate_id, user_id)
    est.deleted = True
    db.commit()
    return {"message": "Estimate deleted."}


async def duplicate_estimate(
    estimate_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
) -> dict:
    """POST /api/estimates/{id}/duplicate — clone project_info to a new estimate."""
    est = _require_estimate(db, estimate_id, user_id)
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user id.")

    new_est = Estimate(
        user_id=uid,
        project_name=f"Copy of {est.project_name or 'Unnamed'}",
        status="in_progress",
        project_info=est.project_info,
    )
    db.add(new_est)
    db.commit()
    db.refresh(new_est)
    return {"id": str(new_est.id), "project_name": new_est.project_name, "status": new_est.status}


async def get_dashboard_summary(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
) -> dict:
    """GET /api/dashboard/summary — summary cards for dashboard (NEW-DASH-01)."""
    from datetime import datetime, timezone
    from calendar import monthrange

    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        return {}

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    base_q = db.query(Estimate).filter(
        Estimate.user_id == uid, Estimate.deleted == False  # noqa: E712
    )

    total = base_q.count()
    this_month = base_q.filter(Estimate.created_at >= month_start).count()

    completed = base_q.filter(Estimate.status == "completed", Estimate.confidence.isnot(None))
    conf_values = [e.confidence for e in completed.all() if e.confidence is not None]
    avg_confidence = round(sum(conf_values) / len(conf_values), 4) if conf_values else None

    total_values = [e.grand_total for e in base_q.all() if e.grand_total is not None]
    total_value = round(sum(total_values), 2) if total_values else 0.0

    return {
        "total_estimates": total,
        "estimates_this_month": this_month,
        "average_confidence": avg_confidence,
        "total_estimated_value": total_value,
    }
