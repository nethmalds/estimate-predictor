"""Pydantic schemas for estimate endpoints (NEW-DASH-13 to 16)."""
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
