from fastapi import HTTPException
from pydantic import BaseModel

from orchestration.floorplan_workflow import run_floorplan_workflow


class FloorPlanOCRRequest(BaseModel):
    image_path: str


def extract_floorplan_dimensions(payload: FloorPlanOCRRequest):
    try:
        return run_floorplan_workflow(payload.image_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ImportError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
