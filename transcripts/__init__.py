"""
Robust transcript fetching system with EdmundSEC primary + Google fallback.

Main entry point: get_transcript(query: TranscriptQuery) -> TranscriptResult
"""
from .models import (
    TranscriptQuery,
    TranscriptCandidate,
    TranscriptResult,
)
from .orchestrator import get_transcript

__all__ = [
    "TranscriptQuery",
    "TranscriptCandidate",
    "TranscriptResult",
    "get_transcript",
]
