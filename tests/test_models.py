"""
Tests for data models.
"""
import pytest
from datetime import date
from transcripts.models import TranscriptQuery, TranscriptCandidate, TranscriptResult


def test_transcript_query_minimal():
    """Test creating minimal query."""

    query = TranscriptQuery(ticker="AAPL")

    assert query.ticker == "AAPL"
    assert query.company_name is None
    assert query.event_date is None
    assert query.event_hint is None
    assert query.event_type == "earnings"  # Default


def test_transcript_query_full():
    """Test creating full query."""

    query = TranscriptQuery(
        ticker="FI",
        company_name="Fiserv, Inc.",
        event_date=date(2025, 11, 12),
        event_hint="KBW Fintech Conference",
        event_type="conference",
    )

    assert query.ticker == "FI"
    assert query.company_name == "Fiserv, Inc."
    assert query.event_date == date(2025, 11, 12)
    assert query.event_hint == "KBW Fintech Conference"
    assert query.event_type == "conference"


def test_transcript_candidate_defaults():
    """Test candidate with defaults."""

    candidate = TranscriptCandidate(provider="TEST")

    assert candidate.provider == "TEST"
    assert candidate.source_url is None
    assert candidate.text is None
    assert candidate.score_transcript_shape == 0.0
    assert candidate.score_date_match == 0.0
    assert candidate.score_company_match == 0.0
    assert candidate.overall_confidence == 0.0
    assert candidate.notes == []


def test_transcript_candidate_with_scores():
    """Test candidate with scoring."""

    candidate = TranscriptCandidate(
        provider="EDMUNDSEC",
        source_url="https://example.com/transcript",
        text="Sample transcript text...",
        score_transcript_shape=0.8,
        score_date_match=1.0,
        score_company_match=0.7,
        overall_confidence=0.825,
    )

    assert candidate.provider == "EDMUNDSEC"
    assert candidate.source_url == "https://example.com/transcript"
    assert candidate.text == "Sample transcript text..."
    assert candidate.score_transcript_shape == 0.8
    assert candidate.score_date_match == 1.0
    assert candidate.score_company_match == 0.7
    assert candidate.overall_confidence == 0.825


def test_transcript_result_success():
    """Test successful result."""

    query = TranscriptQuery(ticker="AAPL")
    candidate = TranscriptCandidate(
        provider="TEST",
        text="Sample transcript",
        overall_confidence=0.85,
    )

    result = TranscriptResult(
        success=True,
        best_candidate=candidate,
        all_candidates=[candidate],
        query=query,
        error=None,
        logs=["Step 1", "Step 2"],
    )

    assert result.success is True
    assert result.best_candidate == candidate
    assert len(result.all_candidates) == 1
    assert result.query == query
    assert result.error is None
    assert len(result.logs) == 2


def test_transcript_result_failure():
    """Test failed result."""

    query = TranscriptQuery(ticker="XYZ")

    result = TranscriptResult(
        success=False,
        best_candidate=None,
        all_candidates=[],
        query=query,
        error="No transcripts found",
        logs=["Tried EdmundSEC", "Tried Google", "No results"],
    )

    assert result.success is False
    assert result.best_candidate is None
    assert len(result.all_candidates) == 0
    assert result.error == "No transcripts found"
    assert len(result.logs) == 3


def test_candidate_notes_appending():
    """Test that notes can be appended."""

    candidate = TranscriptCandidate(provider="TEST")

    candidate.notes.append("Note 1")
    candidate.notes.append("Note 2")
    candidate.notes.extend(["Note 3", "Note 4"])

    assert len(candidate.notes) == 4
    assert candidate.notes[0] == "Note 1"
    assert candidate.notes[3] == "Note 4"
