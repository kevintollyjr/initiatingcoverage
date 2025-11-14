"""
Tests for scoring module.
"""
import pytest
from datetime import date
from transcripts.models import TranscriptQuery, TranscriptCandidate
from transcripts.scoring import (
    score_transcript_shape,
    score_date_match,
    score_company_match,
    compute_overall_confidence,
    score_candidate,
)


def test_shape_score_real_transcript():
    """Test that a real-looking transcript gets a high shape score."""

    text = """
    Fiserv, Inc. (NYSE: FI) Q3 2025 Earnings Call
    November 1, 2025

    Operator

    Good morning, and welcome to the Fiserv Third Quarter 2025 Earnings Conference Call.

    Forward-Looking Statements

    This call contains forward-looking statements within the meaning of the Safe Harbor
    provisions of the Private Securities Litigation Reform Act of 1995.

    CEO - Frank Bisignano

    Good morning everyone, and thank you for joining us today...

    Question-and-Answer Session

    Operator

    We will now begin the question-and-answer session...
    """

    score, notes = score_transcript_shape(text)

    assert score >= 0.7  # Should be high score
    assert any("Operator" in note for note in notes)
    assert any("Q&A" in note or "question" in note.lower() for note in notes)
    assert any("forward-looking" in note.lower() for note in notes)


def test_shape_score_non_transcript():
    """Test that non-transcript text gets low score."""

    text = "This is just a short article about a company. Nothing special here."

    score, notes = score_transcript_shape(text)

    assert score < 0.3  # Should be low score


def test_date_match_exact():
    """Test exact date match."""

    event_date = date(2025, 11, 1)
    candidate_date = date(2025, 11, 1)

    score, notes = score_date_match(event_date, candidate_date)

    assert score == 1.0
    assert any("exact" in note.lower() for note in notes)


def test_date_match_close():
    """Test close date match."""

    event_date = date(2025, 11, 1)
    candidate_date = date(2025, 11, 3)  # 2 days off

    score, notes = score_date_match(event_date, candidate_date)

    assert 0.4 <= score <= 0.6  # Within 3 days
    assert any("2 days" in note for note in notes)


def test_date_match_far():
    """Test far-off date."""

    event_date = date(2025, 11, 1)
    candidate_date = date(2025, 10, 1)  # 31 days off

    score, notes = score_date_match(event_date, candidate_date)

    assert score == 0.0
    assert any("week" in note.lower() for note in notes)


def test_date_match_no_event_date():
    """Test neutral score when no event date provided."""

    score, notes = score_date_match(None, date(2025, 11, 1))

    assert score == 0.5  # Neutral
    assert any("no event date" in note.lower() for note in notes)


def test_company_match_ticker_found():
    """Test company match when ticker is present."""

    query = TranscriptQuery(
        ticker="FI",
        company_name="Fiserv, Inc.",
    )

    candidate = TranscriptCandidate(
        provider="TEST",
        text="Fiserv, Inc. (NYSE: FI) Third Quarter 2025 Earnings...",
    )

    score, notes = score_company_match(query, candidate)

    assert score >= 0.4  # Ticker match
    assert any("ticker" in note.lower() and "FI" in note for note in notes)


def test_company_match_company_name_found():
    """Test company match when company name is present."""

    query = TranscriptQuery(
        ticker="AAPL",
        company_name="Apple Inc.",
    )

    candidate = TranscriptCandidate(
        provider="TEST",
        text="Apple Inc. reported strong quarterly results...",
    )

    score, notes = score_company_match(query, candidate)

    assert score >= 0.3  # Company name match
    assert any("company name" in note.lower() for note in notes)


def test_company_match_nothing_found():
    """Test low score when no matches."""

    query = TranscriptQuery(
        ticker="MSFT",
        company_name="Microsoft Corporation",
    )

    candidate = TranscriptCandidate(
        provider="TEST",
        text="Some random text about different companies...",
    )

    score, notes = score_company_match(query, candidate)

    assert score == 0.0
    assert any("no company" in note.lower() or "no match" in note.lower() for note in notes)


def test_overall_confidence():
    """Test overall confidence calculation."""

    # High scores across the board
    shape = 0.8
    date_score = 1.0
    company = 0.7

    overall = compute_overall_confidence(shape, date_score, company)

    # Overall = 0.5*0.8 + 0.25*1.0 + 0.25*0.7 = 0.4 + 0.25 + 0.175 = 0.825
    assert 0.82 <= overall <= 0.83


def test_score_candidate_integration():
    """Test full candidate scoring."""

    query = TranscriptQuery(
        ticker="FI",
        company_name="Fiserv, Inc.",
        event_date=date(2025, 11, 1),
        event_type="earnings",
    )

    text = """
    Fiserv, Inc. (NYSE: FI)
    Third Quarter 2025 Earnings Conference Call
    November 1, 2025

    Operator

    Good morning and welcome...

    Forward-Looking Statements

    This presentation contains forward-looking statements...

    """ + ("Lorem ipsum " * 500)  # Make it long enough

    candidate = TranscriptCandidate(
        provider="TEST",
        text=text,
        parsed_date=date(2025, 11, 1),
        parsed_ticker="FI",
        parsed_company_name="Fiserv, Inc.",
    )

    score_candidate(candidate, query)

    # Should have high scores
    assert candidate.score_transcript_shape >= 0.5
    assert candidate.score_date_match >= 0.9  # Exact date
    assert candidate.score_company_match >= 0.5
    assert candidate.overall_confidence >= 0.6

    # Should have notes
    assert len(candidate.notes) > 0
