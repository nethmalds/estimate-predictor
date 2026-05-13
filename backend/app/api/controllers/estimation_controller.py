from fastapi import Request
from pydantic import BaseModel, Field

from app.api.middleware.rate_limit import limiter, _dev_limit
from services.rag_process.service import service


# ─── Request models ───────────────────────────────────────────────────────────

class MatchRequest(BaseModel):
    boq_text: str = Field(..., min_length=3)


# ─── Endpoint handlers ────────────────────────────────────────────────────────

@limiter.limit(_dev_limit("20/minute"))
def match_boq(request: Request, payload: MatchRequest):
    """RAG single-item match — returns best BSR match for a BOQ description."""
    return service.match_boq_item(payload.boq_text)
