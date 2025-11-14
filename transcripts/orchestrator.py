"""
Main orchestrator for transcript fetching.
"""
import logging
import os
from typing import Optional

from .models import TranscriptQuery, TranscriptResult, TranscriptCandidate
from .edmundsec_client import EdmundSecClient
from .google_fallback import GoogleFallbackProvider
from .scoring import score_candidate

logger = logging.getLogger(__name__)

# Confidence thresholds
EDMUNDSEC_CONFIDENCE_THRESHOLD = 0.7
FALLBACK_CONFIDENCE_THRESHOLD = 0.6
MIN_ACCEPTABLE_CONFIDENCE = 0.4


def get_transcript(query: TranscriptQuery) -> TranscriptResult:
    """
    Main entry point: fetch transcript for given query.

    Process:
    1. Try EdmundSEC (authenticated) as primary source
    2. If no high-confidence match, try Google fallback
    3. Score all candidates and return best match
    4. Return comprehensive diagnostics

    Args:
        query: TranscriptQuery with ticker, date, event info

    Returns:
        TranscriptResult with success flag, best candidate, all candidates, and logs
    """
    logs = []
    all_candidates = []

    logs.append(f"Starting transcript search for {query.ticker}")
    logs.append(f"Event type: {query.event_type}, Date: {query.event_date}, Hint: {query.event_hint}")

    # ============================================================
    # PHASE 1: EdmundSEC (Primary Source)
    # ============================================================
    try:
        edmundsec_candidates = _try_edmundsec(query, logs)
        all_candidates.extend(edmundsec_candidates)

        # Check if we have a high-confidence EdmundSEC result
        high_conf_edmundsec = [c for c in edmundsec_candidates
                               if c.overall_confidence >= EDMUNDSEC_CONFIDENCE_THRESHOLD]

        if high_conf_edmundsec:
            best = max(high_conf_edmundsec, key=lambda c: c.overall_confidence)
            logs.append(f"EdmundSEC found high-confidence match: {best.overall_confidence:.2f}")
            return TranscriptResult(
                success=True,
                best_candidate=best,
                all_candidates=all_candidates,
                query=query,
                error=None,
                logs=logs,
            )
        else:
            logs.append(f"EdmundSEC yielded {len(edmundsec_candidates)} candidates, none with confidence >= {EDMUNDSEC_CONFIDENCE_THRESHOLD}")

    except Exception as e:
        logs.append(f"EdmundSEC error: {str(e)}")
        logger.error(f"EdmundSEC error: {e}", exc_info=True)

    # ============================================================
    # PHASE 2: Google Fallback
    # ============================================================
    try:
        logs.append("Falling back to Google search...")
        google_candidates = _try_google_fallback(query, logs)
        all_candidates.extend(google_candidates)
        logs.append(f"Google fallback found {len(google_candidates)} candidates")

    except Exception as e:
        logs.append(f"Google fallback error: {str(e)}")
        logger.error(f"Google fallback error: {e}", exc_info=True)

    # ============================================================
    # PHASE 3: Select Best Candidate
    # ============================================================
    if not all_candidates:
        logs.append("No candidates found from any source")
        return TranscriptResult(
            success=False,
            best_candidate=None,
            all_candidates=[],
            query=query,
            error="No transcript candidates found for this query",
            logs=logs,
        )

    # Sort by confidence
    all_candidates.sort(key=lambda c: c.overall_confidence, reverse=True)
    best = all_candidates[0]

    logs.append(f"Best candidate: {best.provider}, confidence: {best.overall_confidence:.2f}")

    # Check if best candidate meets minimum threshold
    if best.overall_confidence >= MIN_ACCEPTABLE_CONFIDENCE:
        logs.append(f"Returning transcript from {best.provider}")
        return TranscriptResult(
            success=True,
            best_candidate=best,
            all_candidates=all_candidates,
            query=query,
            error=None,
            logs=logs,
        )
    else:
        logs.append(f"Best candidate confidence {best.overall_confidence:.2f} below threshold {MIN_ACCEPTABLE_CONFIDENCE}")
        return TranscriptResult(
            success=False,
            best_candidate=best,  # Still return it for inspection
            all_candidates=all_candidates,
            query=query,
            error=f"No high-confidence transcript found (best: {best.overall_confidence:.2f})",
            logs=logs,
        )


def _try_edmundsec(query: TranscriptQuery, logs: list[str]) -> list[TranscriptCandidate]:
    """
    Try to fetch transcripts from EdmundSEC.
    Returns: list of scored TranscriptCandidate objects
    """
    logs.append("Attempting EdmundSEC...")

    # Get credentials from environment
    username = os.getenv("EDMUNDSEC_USERNAME")
    password = os.getenv("EDMUNDSEC_PASSWORD")

    if not username or not password:
        logs.append("EdmundSEC credentials not found in environment (EDMUNDSEC_USERNAME, EDMUNDSEC_PASSWORD)")
        return []

    try:
        client = EdmundSecClient(username, password)
        client.login()
        logs.append("EdmundSEC login successful")

        # Find candidate documents
        candidate_docs = client.find_candidate_docs_for_query(query)
        logs.append(f"EdmundSEC found {len(candidate_docs)} candidate documents")

        if not candidate_docs:
            return []

        # Download and parse top candidates
        candidates = []
        for doc in candidate_docs[:5]:  # Top 5 docs
            try:
                candidate = client.download_and_parse_doc(doc)

                # Score the candidate
                score_candidate(candidate, query)

                candidates.append(candidate)
                logs.append(f"EdmundSEC candidate: {doc['title'][:50]}... (confidence: {candidate.overall_confidence:.2f})")

            except Exception as e:
                logs.append(f"Error processing EdmundSEC doc: {str(e)}")
                logger.error(f"Error processing EdmundSEC doc: {e}", exc_info=True)

        return candidates

    except Exception as e:
        logs.append(f"EdmundSEC failed: {str(e)}")
        logger.error(f"EdmundSEC failed: {e}", exc_info=True)
        return []


def _try_google_fallback(query: TranscriptQuery, logs: list[str]) -> list[TranscriptCandidate]:
    """
    Try to fetch transcripts via Google search.
    Returns: list of scored TranscriptCandidate objects
    """
    logs.append("Attempting Google fallback...")

    try:
        provider = GoogleFallbackProvider()
        candidates = provider.find_candidates(query)

        # Score each candidate
        for candidate in candidates:
            score_candidate(candidate, query)
            logs.append(f"Google candidate: {candidate.source_url[:60]}... (confidence: {candidate.overall_confidence:.2f})")

        return candidates

    except Exception as e:
        logs.append(f"Google fallback failed: {str(e)}")
        logger.error(f"Google fallback failed: {e}", exc_info=True)
        return []
