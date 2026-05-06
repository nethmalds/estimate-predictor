"""Clarification process service — public facade.

Retained exports (used by estimation_pipeline.py and form_controller.py):
    apply_defaults      — fills non-MVED fields with Sri Lankan construction norms
    merge_parameters    — merges override parameters into project_info

Removed (chat-only, no longer called):
    extract_project_info                — LLM text-description extraction
    check_requirements                  — LLM requirements check
    extract_project_info_with_clarifications — multi-turn LLM chat
    find_missing_fields                 — clarification gate check
    build_clarification_questions       — question list builder
    normalize_ceiling_type              — chat answer parser
"""
from services.clarification_process.clarification_agent import (
    apply_defaults,
    merge_parameters,
)

__all__ = [
    "apply_defaults",
    "merge_parameters",
]
