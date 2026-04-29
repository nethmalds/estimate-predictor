import os

from fastapi import APIRouter

from app.api.controllers.estimation_controller import (
	start_estimation_stream,
	stream_estimation,
	get_documents,
	ingest_bsr,
	match_boq,
	diagnose_bsr,
)
from app.api.controllers.clarification_controller import (
	start_clarification,
	submit_clarification_answer,
	stream_clarification,
)
from app.api.controllers.project_controller import extract_floorplan_dimensions

router = APIRouter(prefix="/api")

router.post("/match-boq")(match_boq)
router.post("/ingest-bsr")(ingest_bsr)
router.post("/rag/diagnose")(diagnose_bsr)
router.post("/estimate-project/stream/start")(start_estimation_stream)
router.get("/estimate-project/stream/{session_id}")(stream_estimation)
router.post("/estimate-project/clarification/start")(start_clarification)
router.post("/estimate-project/clarification/{session_id}/answer")(submit_clarification_answer)
router.get("/estimate-project/clarification/stream/{session_id}")(stream_clarification)
router.post("/floorplan-ocr")(extract_floorplan_dimensions)
router.get("/documents/")(get_documents)

# Diagnostic routes — only registered in development environment.
# In production (ENV != 'development') these routes simply do not exist,
# returning 404 by definition rather than relying on auth middleware.
if os.getenv("ENV", "development").lower() == "development":
	from app.api.controllers.diagnostic_controller import (
		stream_pipeline_trace,
		get_pipeline_snapshot,
		get_pipeline_steps,
	)
	router.get("/pipeline/trace/{session_id}")(stream_pipeline_trace)    # SSE live stream
	router.get("/pipeline/snapshot/{session_id}")(get_pipeline_snapshot) # REST full trace
	router.get("/pipeline/steps")(get_pipeline_steps)                    # static step registry

__all__ = ["router"]
