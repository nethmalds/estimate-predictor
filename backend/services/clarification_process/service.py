"""Clarification process service — public facade.

All cross-service communication goes through this module.  Internal
implementation modules (llm_client, clarification_agent) are not
imported directly by other services.
"""
from services.clarification_process.llm_client import (
    extract_project_info,
    check_requirements,
    extract_project_info_with_clarifications,
)
from services.clarification_process.clarification_agent import (
    find_missing_fields,
    build_clarification_questions,
    merge_parameters,
    normalize_ceiling_type,
)

__all__ = [
    "extract_project_info",
    "check_requirements",
    "extract_project_info_with_clarifications",
    "find_missing_fields",
    "build_clarification_questions",
    "merge_parameters",
    "normalize_ceiling_type",
]
