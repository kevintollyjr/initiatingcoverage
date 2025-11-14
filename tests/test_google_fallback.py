"""
Tests for Google fallback provider.
"""
import pytest
from datetime import date
from transcripts.models import TranscriptQuery
from transcripts.google_fallback import GoogleFallbackProvider


def test_generate_search_queries():
    """Test search query generation."""

    query = TranscriptQuery(
        ticker="FI",
        company_name="Fiserv, Inc.",
        event_date=date(2025, 11, 12),
        event_hint="KBW Fintech Conference",
        event_type="conference",
    )

    provider = GoogleFallbackProvider()
    queries = provider._generate_search_queries(query)

    # Should have multiple queries
    assert len(queries) > 0

    # First query should be most specific
    assert "Fiserv" in queries[0]
    assert "KBW" in queries[0]
    assert "transcript" in queries[0].lower()


def test_generate_search_queries_minimal():
    """Test query generation with minimal info."""

    query = TranscriptQuery(
        ticker="AAPL",
        event_type="earnings",
    )

    provider = GoogleFallbackProvider()
    queries = provider._generate_search_queries(query)

    assert len(queries) > 0
    assert any("AAPL" in q for q in queries)
    assert any("transcript" in q.lower() for q in queries)


def test_is_transcript_url_valid():
    """Test transcript URL detection."""

    provider = GoogleFallbackProvider()

    # Valid transcript URLs
    valid_urls = [
        "https://www.fool.com/earnings/call-transcripts/2025/11/12/fiserv-fi-q3-2025-transcript/",
        "https://seekingalpha.com/article/4567890-fiserv-fi-q3-2025-earnings-call-transcript",
        "https://finance.yahoo.com/news/fiserv-earnings-transcript-123456.html",
        "https://investors.fiserv.com/transcripts/2025-q3-earnings",
    ]

    for url in valid_urls:
        assert provider._is_transcript_url(url), f"Should accept: {url}"

    # Invalid URLs
    invalid_urls = [
        "https://www.google.com/search?q=transcript",  # Search page
        "https://www.wikipedia.org/wiki/Earnings_call",  # Wikipedia
        "https://twitter.com/company/status/123",  # Social media
        "https://news.site.com/article-about-stocks",  # No transcript indicator
    ]

    for url in invalid_urls:
        assert not provider._is_transcript_url(url), f"Should reject: {url}"


def test_parse_date():
    """Test date parsing."""

    provider = GoogleFallbackProvider()

    # Test various formats
    assert provider._parse_date("2025-11-12") == date(2025, 11, 12)
    assert provider._parse_date("11/12/2025") == date(2025, 11, 12)
    assert provider._parse_date("November 12, 2025") == date(2025, 11, 12)
    assert provider._parse_date("Nov 12, 2025") == date(2025, 11, 12)

    # Invalid format
    assert provider._parse_date("not a date") is None
    assert provider._parse_date("") is None
    assert provider._parse_date(None) is None


def test_extract_metadata():
    """Test metadata extraction from transcript text."""

    provider = GoogleFallbackProvider()

    from transcripts.models import TranscriptCandidate

    text = """
    Fiserv, Inc. (NYSE: FI)
    Third Quarter 2025 Earnings Conference Call
    November 12, 2025

    Good morning and welcome to Fiserv's earnings call...
    """

    candidate = TranscriptCandidate(
        provider="GOOGLE_FALLBACK",
        text=text,
    )

    provider._extract_metadata(candidate, "https://example.com/transcript")

    assert candidate.parsed_ticker == "FI"
    assert "Fiserv" in (candidate.parsed_company_name or "")
    assert candidate.parsed_date == date(2025, 11, 12)


def test_parse_html():
    """Test HTML parsing."""

    provider = GoogleFallbackProvider()

    html = """
    <html>
    <head><title>Earnings Transcript</title></head>
    <body>
        <nav>Navigation</nav>
        <article>
            <p>This is the first paragraph of the transcript.</p>
            <p>This is the second paragraph with more content.</p>
            <p>And a third paragraph here.</p>
        </article>
        <footer>Copyright 2025</footer>
    </body>
    </html>
    """

    text = provider._parse_html(html, "https://example.com")

    # Should extract article content
    assert "first paragraph" in text
    assert "second paragraph" in text
    assert "third paragraph" in text

    # Should exclude nav and footer
    assert "Navigation" not in text
    assert "Copyright" not in text


def test_parse_html_no_content():
    """Test HTML parsing when no content found."""

    provider = GoogleFallbackProvider()

    html = """
    <html>
    <body>
        <div>Short text</div>
    </body>
    </html>
    """

    text = provider._parse_html(html, "https://example.com")

    # Should still extract something (even if short)
    assert isinstance(text, str)
