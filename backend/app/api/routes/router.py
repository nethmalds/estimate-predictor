import os

from fastapi import APIRouter

from app.api.controllers.estimation_controller import (
    get_documents,
    match_boq,
    diagnose_bsr,
)
from app.api.controllers.form_controller import (
    validate_form_payload,
    submit_form,
    stream_form_estimation,
)
from app.api.controllers.project_controller import extract_floorplan_dimensions

router = APIRouter(prefix="/api")

# ─── RAG / BSR utilities ──────────────────────────────────────────────────────
router.post("/match-boq")(match_boq)
router.post("/rag/diagnose")(diagnose_bsr)
router.get("/documents/")(get_documents)

# ─── Wizard form flow (primary route) ────────────────────────────────────────
router.post("/estimate-project/form/validate")(validate_form_payload)
router.post("/estimate-project/form/submit")(submit_form)
router.get("/estimate-project/form/stream/{session_id}")(stream_form_estimation)

# ─── Floorplan OCR utility ────────────────────────────────────────────────────
router.post("/floorplan-ocr")(extract_floorplan_dimensions)

# ─── Diagnostic routes — development only ────────────────────────────────────
# In production (ENV != "development") these routes simply do not exist,
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
