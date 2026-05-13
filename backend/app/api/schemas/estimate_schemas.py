"""Pydantic schemas for estimate endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class EstimateListItem(BaseModel):
    id: str
    project_name: str | None
    status: str
    confidence: float | None
    grand_total: float | None
    item_count: int | None
    created_at: datetime
    updated_at: datetime
    building_type: str | None = None
    floors: int | None = None
    built_up_area: str | None = None
    floorplan_accepted: bool | None = None
    # Lifecycle fields exposed in list view
    progress: dict | None = None
    error_message: str | None = None
    cancelled_at: datetime | None = None
    regenerated_from_estimate_id: str | None = None

    model_config = {"from_attributes": True}


class EstimateDetail(BaseModel):
    id: str
    project_name: str | None
    notes: str | None
    status: str
    project_info: dict | None
    result: dict | None
    confidence: float | None
    grand_total: float | None
    item_count: int | None
    created_at: datetime
    updated_at: datetime
    # Lifecycle fields
    progress: dict | None = None
    error_message: str | None = None
    cancelled_at: datetime | None = None
    regenerated_from_estimate_id: str | None = None
    wizard_payload: dict | None = None

    model_config = {"from_attributes": True}


class EstimatePatchRequest(BaseModel):
    project_name: str | None = None
    notes: str | None = None


class EstimateListResponse(BaseModel):
    estimates: list[EstimateListItem]
    total: int
    page: int
    page_size: int


class DashboardSummary(BaseModel):
    total_estimates: int
    estimates_this_month: int
    average_confidence: float | None
    total_estimated_value: float


class CancelEstimateResponse(BaseModel):
    id: str
    status: str
    cancelled_at: datetime | None = None


class RegenerateEstimateResponse(BaseModel):
    id: str
    status: str
    project_name: str | None
    created_at: datetime
    regenerated_from_estimate_id: str | None = None
