#!/usr/bin/env python3
"""
Demo script for transcript fetching system.
"""
import sys
from datetime import date
from transcripts import get_transcript, TranscriptQuery


def main():
    """Run demo transcript fetch."""

    # Example 1: Conference transcript
    print("=" * 80)
    print("EXAMPLE 1: Conference Transcript")
    print("=" * 80)

    query1 = TranscriptQuery(
        ticker="FI",
        company_name="Fiserv, Inc.",
        event_date=date(2025, 11, 12),
        event_hint="KBW Fintech Payments Conference",
        event_type="conference",
    )

    result1 = fetch_and_display(query1)

    # Example 2: Earnings call
    print("\n\n" + "=" * 80)
    print("EXAMPLE 2: Earnings Call")
    print("=" * 80)

    query2 = TranscriptQuery(
        ticker="AAPL",
        company_name="Apple Inc.",
        event_date=date(2025, 10, 31),
        event_hint="Q4 2025 Earnings",
        event_type="earnings",
    )

    result2 = fetch_and_display(query2)

    # Example 3: Minimal info
    print("\n\n" + "=" * 80)
    print("EXAMPLE 3: Minimal Info (ticker only)")
    print("=" * 80)

    query3 = TranscriptQuery(
        ticker="MSFT",
        event_type="earnings",
    )

    result3 = fetch_and_display(query3)


def fetch_and_display(query: TranscriptQuery) -> any:
    """Fetch transcript and display results."""

    print(f"\nQuery:")
    print(f"  Ticker: {query.ticker}")
    print(f"  Company: {query.company_name or 'N/A'}")
    print(f"  Event Date: {query.event_date or 'N/A'}")
    print(f"  Event Hint: {query.event_hint or 'N/A'}")
    print(f"  Event Type: {query.event_type}")

    print("\nFetching transcript...")
    result = get_transcript(query)

    print(f"\n{'SUCCESS' if result.success else 'FAILED'}")

    if result.success and result.best_candidate:
        candidate = result.best_candidate
        print(f"\nBest Candidate:")
        print(f"  Provider: {candidate.provider}")
        print(f"  URL: {candidate.source_url}")
        print(f"  Overall Confidence: {candidate.overall_confidence:.2f}")
        print(f"    - Shape Score: {candidate.score_transcript_shape:.2f}")
        print(f"    - Date Score: {candidate.score_date_match:.2f}")
        print(f"    - Company Score: {candidate.score_company_match:.2f}")

        if candidate.parsed_title:
            print(f"  Parsed Title: {candidate.parsed_title[:80]}")
        if candidate.parsed_date:
            print(f"  Parsed Date: {candidate.parsed_date}")
        if candidate.parsed_ticker:
            print(f"  Parsed Ticker: {candidate.parsed_ticker}")
        if candidate.parsed_company_name:
            print(f"  Parsed Company: {candidate.parsed_company_name}")

        if candidate.text:
            print(f"\n  Transcript Length: {len(candidate.text):,} characters")
            print(f"\n  Preview (first 500 chars):")
            print("  " + "-" * 76)
            preview = candidate.text[:500].replace('\n', '\n  ')
            print(f"  {preview}")
            if len(candidate.text) > 500:
                print(f"  ... ({len(candidate.text) - 500:,} more characters)")
            print("  " + "-" * 76)

        print(f"\n  Diagnostic Notes ({len(candidate.notes)}):")
        for note in candidate.notes[:10]:  # First 10 notes
            print(f"    - {note}")
        if len(candidate.notes) > 10:
            print(f"    ... ({len(candidate.notes) - 10} more notes)")

    else:
        print(f"\nError: {result.error}")

    print(f"\nAll Candidates Found: {len(result.all_candidates)}")
    for i, cand in enumerate(result.all_candidates, 1):
        print(f"  {i}. {cand.provider} - Confidence: {cand.overall_confidence:.2f} - {cand.source_url[:60]}...")

    print(f"\nExecution Log ({len(result.logs)} entries):")
    for log in result.logs:
        print(f"  {log}")

    return result


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
