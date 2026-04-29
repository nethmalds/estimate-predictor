"""Item generation service — public facade.

All cross-service communication goes through this module.  Internal
implementation modules (boq_builder, item_predictor, llm_client) are not
imported directly by other services.
"""
from services.item_gen_process.boq_builder import build_final_boq_items

__all__ = ["build_final_boq_items"]

