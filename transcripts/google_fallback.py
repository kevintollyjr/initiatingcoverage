"""
Google-based fallback provider for transcript fetching.
"""
import logging
import re
import time
import urllib.parse
from datetime import datetime, date
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .models import TranscriptCandidate, TranscriptQuery

logger = logging.getLogger(__name__)


class GoogleFallbackProvider:
    """
    Fallback provider that uses Google search to find transcripts.
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        })

    def find_candidates(self, query: TranscriptQuery) -> list[TranscriptCandidate]:
        """
        Search Google for transcript candidates.
        Returns: list of TranscriptCandidate objects
        """
        candidates = []
        search_queries = self._generate_search_queries(query)

        logger.info(f"Google fallback: trying {len(search_queries)} search queries")

        for search_query in search_queries:
            urls = self._search_google(search_query)
            logger.info(f"Found {len(urls)} URLs for query: {search_query[:50]}...")

            for url in urls[:3]:  # Top 3 results per query
                candidate = self._fetch_and_parse_url(url, query)
                if candidate and candidate.text:
                    candidates.append(candidate)

                time.sleep(1)  # Rate limiting

            if len(candidates) >= 5:  # Stop if we have enough
                break

            time.sleep(2)  # Rate limiting between queries

        logger.info(f"Google fallback found {len(candidates)} candidates")
        return candidates

    def _generate_search_queries(self, query: TranscriptQuery) -> list[str]:
        """Generate prioritized list of search queries."""
        queries = []

        # Format date for queries if available
        date_str = ""
        if query.event_date:
            date_str = query.event_date.strftime("%Y")

        # Priority 1: Company + event hint
        if query.company_name and query.event_hint:
            queries.append(f'"{query.company_name}" "{query.event_hint}" transcript {date_str}')

        # Priority 2: Ticker + event hint
        if query.event_hint:
            queries.append(f'{query.ticker} "{query.event_hint}" transcript {date_str}')

        # Priority 3: Company + event type
        if query.company_name:
            if query.event_type == "earnings":
                queries.append(f'"{query.company_name}" earnings call transcript {date_str}')
            elif query.event_type == "conference":
                queries.append(f'"{query.company_name}" conference presentation transcript {date_str}')

        # Priority 4: Ticker + event type
        if query.event_type == "earnings":
            queries.append(f'{query.ticker} earnings call transcript {date_str}')
        elif query.event_type == "conference":
            queries.append(f'{query.ticker} conference presentation transcript {date_str}')

        # Priority 5: Generic fallback
        queries.append(f'{query.ticker} {query.company_name or ""} transcript {date_str}')

        return [q.strip() for q in queries if q.strip()]

    def _search_google(self, search_query: str) -> list[str]:
        """
        Perform Google search and extract result URLs.
        Returns: list of URLs
        """
        try:
            search_url = f"https://www.google.com/search?q={urllib.parse.quote(search_query)}"
            response = self.session.get(search_url, timeout=15)

            if response.status_code != 200:
                logger.warning(f"Google search returned status {response.status_code}")
                return []

            soup = BeautifulSoup(response.text, 'html.parser')
            urls = []

            # Parse Google search results
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')

                # Google wraps URLs like: /url?q=https://...&sa=...
                if '/url?q=' in href:
                    url_match = re.search(r'/url\?q=([^&]+)', href)
                    if url_match:
                        actual_url = urllib.parse.unquote(url_match.group(1))

                        # Filter for transcript-likely URLs
                        if self._is_transcript_url(actual_url):
                            if actual_url not in urls:  # Deduplicate
                                urls.append(actual_url)

            return urls

        except Exception as e:
            logger.error(f"Error searching Google: {e}")
            return []

    def _is_transcript_url(self, url: str) -> bool:
        """Check if URL likely contains a transcript."""
        url_lower = url.lower()

        # Must contain transcript/earnings indicators
        if not any(term in url_lower for term in [
            'transcript', 'earnings', 'conference-call', 'webcast'
        ]):
            return False

        # Prefer known transcript sources
        preferred_domains = [
            'fool.com', 'seekingalpha.com', 'investing.com',
            'yahoo.com', 'finance.yahoo.com', 'sec.gov',
            'investors.', 'investor.', 'ir.'  # Investor relations domains
        ]

        return any(domain in url_lower for domain in preferred_domains)

    def _fetch_and_parse_url(self, url: str, query: TranscriptQuery) -> Optional[TranscriptCandidate]:
        """
        Fetch URL and parse into TranscriptCandidate.
        """
        candidate = TranscriptCandidate(
            provider="GOOGLE_FALLBACK",
            source_url=url,
        )

        try:
            logger.info(f"Fetching: {url}")
            response = self.session.get(url, timeout=30)

            if response.status_code != 200:
                candidate.notes.append(f"HTTP {response.status_code}")
                return candidate

            content_type = response.headers.get('Content-Type', '').lower()

            # Parse based on content type
            if 'pdf' in content_type:
                candidate.text = self._parse_pdf(response.content)
                candidate.raw_bytes = response.content
            else:
                candidate.text = self._parse_html(response.text, url)

            if candidate.text:
                # Extract metadata
                self._extract_metadata(candidate, url)
                candidate.notes.append(f"Fetched from Google result: {len(candidate.text)} chars")
            else:
                candidate.notes.append("Failed to extract transcript text")

        except Exception as e:
            logger.error(f"Error fetching URL {url}: {e}")
            candidate.notes.append(f"Error: {str(e)}")

        return candidate

    def _parse_html(self, html: str, url: str) -> str:
        """Extract transcript text from HTML."""
        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Remove non-content elements
            for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                tag.decompose()

            # Try site-specific selectors first
            content = None

            if 'fool.com' in url:
                content = soup.find('article')
            elif 'seekingalpha.com' in url:
                content = soup.find('div', class_=re.compile(r'sa-art|article-content'))
            elif 'investing.com' in url:
                content = soup.find('div', class_='WYSIWYG')
            elif 'yahoo.com' in url:
                content = soup.find('div', class_='caas-body')

            # Generic fallback selectors
            if not content:
                for selector in [
                    ('article', {}),
                    ('div', {'class': re.compile(r'article|content|transcript|body', re.I)}),
                    ('div', {'id': re.compile(r'article|content|transcript|body', re.I)}),
                    ('main', {}),
                ]:
                    if isinstance(selector, tuple):
                        content = soup.find(*selector)
                    else:
                        content = soup.find(selector)
                    if content:
                        break

            # Last resort: use body
            if not content:
                content = soup.body

            if not content:
                return ""

            # Extract text
            paragraphs = content.find_all(['p', 'div'])
            text_parts = []

            for p in paragraphs:
                text = p.get_text(strip=True)
                if text and len(text) > 20:  # Skip short fragments
                    text_parts.append(text)

            return '\n\n'.join(text_parts)

        except Exception as e:
            logger.error(f"Error parsing HTML: {e}")
            return ""

    def _parse_pdf(self, pdf_bytes: bytes) -> str:
        """Extract text from PDF."""
        try:
            import pdfplumber
            import io

            text_parts = []
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)

            return '\n\n'.join(text_parts)

        except ImportError:
            logger.error("pdfplumber not installed")
            return ""
        except Exception as e:
            logger.error(f"Error parsing PDF: {e}")
            return ""

    def _extract_metadata(self, candidate: TranscriptCandidate, url: str) -> None:
        """Extract metadata from transcript text and URL."""
        if not candidate.text:
            return

        header = candidate.text[:1000]  # First 1000 chars

        # Extract title from first line or heading
        lines = candidate.text.split('\n')
        if lines:
            candidate.parsed_title = lines[0].strip()[:200]

        # Extract ticker
        ticker_match = re.search(r'\((?:NYSE|NASDAQ|AMEX):\s*([A-Z]+)\)', header, re.I)
        if ticker_match:
            candidate.parsed_ticker = ticker_match.group(1).upper()

        # Extract company name
        company_match = re.search(
            r'^\s*([A-Z][A-Za-z\s&,\.]+(?:Inc\.|Corp\.|Corporation|Company|Ltd\.))',
            header,
            re.M
        )
        if company_match:
            candidate.parsed_company_name = company_match.group(1).strip()

        # Extract date
        date_patterns = [
            r'(\w+ \d{1,2},\s*\d{4})',  # November 12, 2025
            r'(\d{1,2}/\d{1,2}/\d{4})',  # 11/12/2025
            r'(\d{4}-\d{2}-\d{2})',     # 2025-11-12
        ]

        for pattern in date_patterns:
            date_match = re.search(pattern, header)
            if date_match:
                parsed = self._parse_date(date_match.group(1))
                if parsed:
                    candidate.parsed_date = parsed
                    break

    def _parse_date(self, date_text: str) -> Optional[date]:
        """Parse date string."""
        if not date_text:
            return None

        formats = [
            '%Y-%m-%d',
            '%m/%d/%Y',
            '%m/%d/%y',
            '%B %d, %Y',
            '%b %d, %Y',
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_text.strip(), fmt).date()
            except ValueError:
                continue

        return None
