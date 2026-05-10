from fastapi import APIRouter, Depends, Query

from app.api.controllers.estimation_controller import match_boq
from app.api.controllers.form_controller import (
    validate_form_payload,
    submit_form,
    stream_form_estimation,
)
from app.api.controllers.project_controller import extract_floorplan_dimensions
from app.api.controllers.auth_controller import (
    register_user,
    login_user,
    forgot_password,
    reset_password,
)
from app.api.controllers.estimates_controller import (
    list_estimates,
    get_estimate,
    patch_estimate,
    delete_estimate,
    duplicate_estimate,
    get_dashboard_summary,
)
from app.api.schemas.auth_schemas import UserRegisterRequest, UserLoginRequest, ForgotPasswordRequest, ResetPasswordRequest
from app.api.schemas.estimate_schemas import EstimatePatchRequest, EstimateListResponse, DashboardSummary
from app.api.schemas.form_schemas import WizardFormPayload, WizardValidateRequest
from infrastructure.data_layer.database.session import get_db_session

router = APIRouter(prefix="/api")

# ─── RAG / BSR utilities ──────────────────────────────────────────────────────
router.post("/match-boq")(match_boq)

# ─── Wizard form flow ─────────────────────────────────────────────────────────
router.post("/estimate-project/form/validate")(validate_form_payload)
router.post("/estimate-project/form/submit")(submit_form)
router.get("/estimate-project/form/stream/{session_id}")(stream_form_estimation)

# ─── Floorplan OCR utility ────────────────────────────────────────────────────
router.post("/floorplan-ocr")(extract_floorplan_dimensions)

# ─── Authentication ───────────────────────────────────────────────────────────
router.post("/users/register")(register_user)
router.post("/auth/login")(login_user)
router.post("/auth/forgot-password")(forgot_password)
router.post("/auth/reset-password")(reset_password)

# ─── Estimates CRUD ───────────────────────────────────────────────────────────
router.get("/estimates")(list_estimates)
router.get("/estimates/{estimate_id}")(get_estimate)
router.patch("/estimates/{estimate_id}")(patch_estimate)
router.delete("/estimates/{estimate_id}")(delete_estimate)
router.post("/estimates/{estimate_id}/duplicate")(duplicate_estimate)
router.get("/dashboard/summary")(get_dashboard_summary)

__all__ = ["router"]
