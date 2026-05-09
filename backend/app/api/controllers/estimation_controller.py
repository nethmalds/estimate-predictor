from pydantic import BaseModel, Field

from services.rag_process.service import service


# ─── Request models ───────────────────────────────────────────────────────────

class MatchRequest(BaseModel):
    boq_text: str = Field(..., min_length=3)


# ─── Endpoint handlers ────────────────────────────────────────────────────────

def match_boq(payload: MatchRequest):
    """RAG single-item match — returns best BSR match for a BOQ description."""
    return service.match_boq_item(payload.boq_text)
