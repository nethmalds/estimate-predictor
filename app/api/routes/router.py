from fastapi import APIRouter

from app.api.controllers.estimation_controller import (
	estimate_project,
	get_documents,
	ingest_bsr,
	match_boq,
)
from app.api.controllers.project_controller import extract_floorplan_dimensions

router = APIRouter(prefix="/api")

router.post("/match-boq")(match_boq)
router.post("/ingest-bsr")(ingest_bsr)
router.post("/estimate-project")(estimate_project)
router.post("/floorplan-ocr")(extract_floorplan_dimensions)
router.get("/documents/")(get_documents)

__all__ = ["router"]
