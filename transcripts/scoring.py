"""
Scoring utilities for transcript candidates.
"""
from datetime import date
from .models import TranscriptQuery, TranscriptCandidate

# Scoring weights (easy to tune)
WEIGHT_SHAPE = 0.5
WEIGHT_DATE = 0.25
WEIGHT_COMPANY = 0.25


def score_transcript_shape(text: str) -> tuple[float, list[str]]:
    """
    Score how much this text looks like a real earnings call transcript.
    Returns: (score 0-1, list of diagnostic notes)
    """
    if not text:
        return 0.0, ["No text content"]

    score = 0.0
    notes = []
    text_lower = text.lower()
    text_len = len(text)

    # Check for operator/moderator
    if "operator" in text_lower:
        score += 0.3
        notes.append("Contains 'Operator' (typical of call transcripts)")

    # Check for Q&A patterns
    if any(pattern in text_lower for pattern in ["question-and-answer", "q&a", "questions and answers"]):
        score += 0.2
        notes.append("Contains Q&A section markers")

    # Check for forward-looking statements (legal boilerplate)
    if any(pattern in text_lower for pattern in ["forward-looking statements", "safe harbor"]):
        score += 0.2
        notes.append("Contains forward-looking statement warnings")

    # Check length (real transcripts are typically substantial)
    if text_len > 5000:
        score += 0.2
        notes.append(f"Substantial length ({text_len:,} characters)")
    elif text_len > 2000:
        score += 0.1
        notes.append(f"Moderate length ({text_len:,} characters)")
    else:
        notes.append(f"Short length ({text_len:,} characters)")

    # Check for speaker labels (CEO:, CFO:, etc.)
    lines = text.split('\n')[:200]  # Check first 200 lines
    speaker_count = sum(1 for line in lines if any(
        label in line for label in ['CEO:', 'CFO:', 'President:', 'Analyst:', '–']
    ))
    if speaker_count >= 5:
        score += 0.1
        notes.append(f"Multiple speaker labels found ({speaker_count})")

    # Cap at 1.0
    score = min(score, 1.0)

    return score, notes


def score_date_match(event_date: date | None, candidate_date: date | None) -> tuple[float, list[str]]:
    """
    Score how well the candidate's date matches the expected event date.
    Returns: (score 0-1, list of diagnostic notes)
    """
    notes = []

    if event_date is None:
        notes.append("No event date provided (neutral score)")
        return 0.5, notes

    if candidate_date is None:
        notes.append("Candidate has no parsed date (weak score)")
        return 0.3, notes

    diff_days = abs((candidate_date - event_date).days)
    notes.append(f"Date difference: {diff_days} days")

    if diff_days == 0:
        notes.append("Exact date match")
        return 1.0, notes
    elif diff_days <= 1:
        notes.append("Within 1 day")
        return 0.8, notes
    elif diff_days <= 3:
        notes.append("Within 3 days")
        return 0.5, notes
    elif diff_days <= 7:
        notes.append("Within 1 week")
        return 0.2, notes
    else:
        notes.append("More than 1 week off")
        return 0.0, notes


def score_company_match(query: TranscriptQuery, candidate: TranscriptCandidate) -> tuple[float, list[str]]:
    """
    Score how well the candidate matches the company/ticker.
    Returns: (score 0-1, list of diagnostic notes)
    """
    score = 0.0
    notes = []

    if not candidate.text:
        notes.append("No text to analyze")
        return 0.0, notes

    # Analyze first 2000 characters (header section typically)
    text_head = candidate.text[:2000].lower()
    ticker_lower = query.ticker.lower()

    # Check for ticker in common patterns
    ticker_patterns = [
        f"({ticker_lower})",
        f"(nyse: {ticker_lower})",
        f"(nasdaq: {ticker_lower})",
        f"ticker: {ticker_lower}",
    ]

    if any(pattern in text_head for pattern in ticker_patterns):
        score += 0.4
        notes.append(f"Ticker '{query.ticker}' found in header")

    # Check for company name (if provided)
    if query.company_name:
        # Normalize company name (remove Inc., Corp., etc.)
        company_normalized = (query.company_name.lower()
                              .replace(', inc.', '')
                              .replace(' inc.', '')
                              .replace(', corp.', '')
                              .replace(' corp.', '')
                              .replace(',', '')
                              .strip())

        if company_normalized in text_head:
            score += 0.3
            notes.append(f"Company name '{query.company_name}' found in header")

    # Check parsed metadata
    if candidate.parsed_ticker and candidate.parsed_ticker.upper() == query.ticker.upper():
        score += 0.2
        notes.append(f"Parsed ticker matches: {candidate.parsed_ticker}")

    if candidate.parsed_company_name and query.company_name:
        if query.company_name.lower() in candidate.parsed_company_name.lower():
            score += 0.1
            notes.append(f"Parsed company name matches: {candidate.parsed_company_name}")

    # Cap at 1.0
    score = min(score, 1.0)

    if score == 0.0:
        notes.append("No company/ticker match found")

    return score, notes


def compute_overall_confidence(shape: float, date_score: float, company_score: float) -> float:
    """
    Compute weighted overall confidence score.
    """
    return (WEIGHT_SHAPE * shape +
            WEIGHT_DATE * date_score +
            WEIGHT_COMPANY * company_score)


def score_candidate(candidate: TranscriptCandidate, query: TranscriptQuery) -> None:
    """
    Score a candidate in-place, populating all score fields and notes.
    """
    # Shape score
    shape_score, shape_notes = score_transcript_shape(candidate.text or "")
    candidate.score_transcript_shape = shape_score
    candidate.notes.extend(shape_notes)

    # Date match score
    date_score, date_notes = score_date_match(query.event_date, candidate.parsed_date)
    candidate.score_date_match = date_score
    candidate.notes.extend(date_notes)

    # Company match score
    company_score, company_notes = score_company_match(query, candidate)
    candidate.score_company_match = company_score
    candidate.notes.extend(company_notes)

    # Overall confidence
    candidate.overall_confidence = compute_overall_confidence(
        shape_score, date_score, company_score
    )
    candidate.notes.append(f"Overall confidence: {candidate.overall_confidence:.2f}")
