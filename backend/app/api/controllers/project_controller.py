from fastapi import HTTPException
from pydantic import BaseModel

from application.pipelines.floorplan_pipeline import execute_floorplan_pipeline


class FloorPlanOCRRequest(BaseModel):
    image_path: str


def extract_floorplan_dimensions(payload: FloorPlanOCRRequest):
    try:
        return execute_floorplan_pipeline(payload.image_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ImportError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
