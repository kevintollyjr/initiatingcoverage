"""
Core data structures for transcript fetching system.
"""
from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class TranscriptQuery:
    """Input parameters for transcript search."""

    ticker: str                           # e.g. "FI"
    company_name: Optional[str] = None    # e.g. "Fiserv, Inc."
    event_date: Optional[date] = None     # when the event took place
    event_hint: Optional[str] = None      # e.g. "KBW Fintech Payments Conference", "Q3 2025 Earnings"
    event_type: str = "earnings"          # "earnings", "conference", "investor_day", "other"


@dataclass
class TranscriptCandidate:
    """A single transcript candidate with scoring and metadata."""

    # Source information
    provider: str                              # "EDMUNDSEC", "GOOGLE_FALLBACK"
    source_url: Optional[str] = None           # full URL to transcript or document

    # Content
    text: Optional[str] = None                 # parsed transcript text (UTF-8)
    raw_bytes: Optional[bytes] = None          # raw bytes of source (HTML/PDF/etc.)

    # Parsed metadata
    parsed_date: Optional[date] = None         # date parsed from transcript content/metadata
    parsed_title: Optional[str] = None
    parsed_ticker: Optional[str] = None
    parsed_company_name: Optional[str] = None

    # Scoring (0-1 scale)
    score_transcript_shape: float = 0.0        # does it look like a real transcript?
    score_date_match: float = 0.0              # does the date correspond to the event?
    score_company_match: float = 0.0           # does the ticker/company look right?
    overall_confidence: float = 0.0            # weighted combination

    # Diagnostics
    notes: list[str] = field(default_factory=list)  # explanations / diagnostics


@dataclass
class TranscriptResult:
    """Final result of transcript fetching operation."""

    success: bool
    best_candidate: Optional[TranscriptCandidate] = None
    all_candidates: list[TranscriptCandidate] = field(default_factory=list)
    query: Optional[TranscriptQuery] = None
    error: Optional[str] = None                # reason if success=False
    logs: list[str] = field(default_factory=list)  # step-by-step log
