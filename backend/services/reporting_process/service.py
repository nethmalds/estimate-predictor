"""Reporting process service — public facade.

This is the single external interface for the reporting_process module.
All callers outside this module must import from here only.
"""
from services.reporting_process.report_builder import build_report
from services.reporting_process.source_summarizer import build_source_summary

__all__ = [
    "build_report",
    "build_source_summary",
]
