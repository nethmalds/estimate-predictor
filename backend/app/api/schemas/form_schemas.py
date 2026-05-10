"""Pydantic request/response schemas for the wizard form endpoints.

Moved from form_controller.py to keep controllers free of model definitions.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FloorAreaRow(BaseModel):
    floor_label: str = Field(..., description="e.g. 'Ground Floor', 'First Floor'")
    area_value: float = Field(..., gt=0, description="Numeric area measurement")
    area_unit: str = Field(default="sqft", pattern="^(sqft|m2)$")


class WizardFormPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Step 1: Project basics
    building_type: Literal["residential", "commercial", "industrial"] = Field(...)
    floor_count: int = Field(..., ge=1, le=100)
    description: str | None = Field(default=None)
    floorplan_urls: list[str] = Field(default_factory=list)

    # Step 2: Floor areas
    floor_areas: list[FloorAreaRow] = Field(..., min_length=1)

    # Step 3: Building program — residential
    bedrooms: int | None = Field(default=None, ge=1, le=50)
    bathrooms: int | None = Field(default=None, ge=1, le=50)

    # Step 3: Building program — commercial
    primary_use_type: str | None = Field(default=None)
    washroom_count: int | None = Field(default=None, ge=1)

    # Step 3: Building program — industrial
    facility_type: str | None = Field(default=None)
    heavy_machinery_load: str | None = Field(default=None)
    hazardous_materials: str | None = Field(default=None)
    specialized_ventilation: str | None = Field(default=None)

    # Step 4: Construction details
    finish_level: str | None = None
    structural_system: str | None = None
    roof_type: str | None = None
    ceiling_type: str | None = None
    location: str | None = None
    soil_condition: str | None = None
    drainage_type: str | None = None
    external_works_scope: str | None = None


class WizardValidateRequest(BaseModel):
    payload: WizardFormPayload
