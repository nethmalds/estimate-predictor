"""Estimates controller — thin HTTP adapter.

All business logic has been moved to app.api.services.estimate_service.EstimateService.
"""
from __future__ import annotations

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from app.api.middleware.auth_dependency import get_current_user_id
from app.api.schemas.estimate_schemas import EstimatePatchRequest
from app.api.services.estimate_service import EstimateService
from infrastructure.data_layer.database.session import get_db_session


async def list_estimates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
) -> dict:
    """GET /api/estimates"""
    return EstimateService(db).list_estimates(user_id, page, page_size)


async def get_estimate(
    estimate_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
) -> dict:
    """GET /api/estimates/{id}"""
    return EstimateService(db).get_estimate(estimate_id, user_id)


async def patch_estimate(
    estimate_id: str,
    body: EstimatePatchRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
) -> dict:
    """PATCH /api/estimates/{id}"""
    return EstimateService(db).patch_estimate(
        estimate_id, user_id,
        project_name=body.project_name,
        notes=body.notes,
    )


async def delete_estimate(
    estimate_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
) -> dict:
    """DELETE /api/estimates/{id}"""
    return EstimateService(db).delete_estimate(estimate_id, user_id)


async def duplicate_estimate(
    estimate_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
) -> dict:
    """POST /api/estimates/{id}/duplicate"""
    return EstimateService(db).duplicate_estimate(estimate_id, user_id)


async def get_dashboard_summary(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
) -> dict:
    """GET /api/dashboard/summary"""
    return EstimateService(db).get_dashboard_summary(user_id)
