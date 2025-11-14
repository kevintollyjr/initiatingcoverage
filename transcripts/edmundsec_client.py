"""
EdmundSEC client for authenticated transcript fetching.
"""
import logging
import re
from datetime import date, datetime
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .models import TranscriptCandidate, TranscriptQuery

logger = logging.getLogger(__name__)


class EdmundSecClient:
    """
    Client for EdmundSEC (authenticated) transcript access.
    """

    BASE_URL = "https://edmundsec.com"  # Adjust if needed

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.session = requests.Session()
        self._logged_in = False

        # Complete browser-like headers
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
        })

    def login(self) -> None:
        """
        Perform login to EdmundSEC.
        Raises exception if login fails.
        """
        if self._logged_in:
            logger.info("Already logged in to EdmundSEC")
            return

        logger.info("Logging in to EdmundSEC...")

        try:
            # Step 1: Get login page to retrieve any CSRF tokens
            login_page_url = f"{self.BASE_URL}/login"  # Adjust actual path
            response = self.session.get(login_page_url, timeout=15)
            response.raise_for_status()

            # Step 2: Parse for CSRF token if present
            soup = BeautifulSoup(response.text, 'html.parser')
            csrf_token = None

            # Common CSRF token patterns
            csrf_input = soup.find('input', {'name': re.compile(r'csrf|token', re.I)})
            if csrf_input:
                csrf_token = csrf_input.get('value')

            # Step 3: POST login credentials
            login_data = {
                'username': self.username,
                'password': self.password,
            }

            if csrf_token:
                login_data['csrf_token'] = csrf_token  # Adjust field name as needed

            response = self.session.post(
                login_page_url,
                data=login_data,
                timeout=15,
                allow_redirects=True
            )

            # Step 4: Verify login success
            # Check for common success indicators
            if response.status_code == 200:
                # Look for username, dashboard, or logout link in response
                if any(indicator in response.text.lower() for indicator in [
                    'logout', 'sign out', self.username.lower(), 'dashboard'
                ]):
                    self._logged_in = True
                    logger.info("Successfully logged in to EdmundSEC")
                    return

            # Login failed
            error_msg = "Login failed: could not verify successful authentication"
            if "invalid" in response.text.lower() or "error" in response.text.lower():
                error_msg = "Login failed: invalid credentials or authentication error"

            raise Exception(error_msg)

        except requests.exceptions.RequestException as e:
            raise Exception(f"Login failed due to network error: {e}")

    def list_transcripts(self, ticker: str, company_name: Optional[str] = None) -> list[dict]:
        """
        List available transcript-like documents for this ticker.
        Returns: list of dicts with keys: url, title, date, type, etc.
        """
        if not self._logged_in:
            self.login()

        logger.info(f"Listing transcripts for {ticker}...")

        try:
            # EdmundSEC likely has a search or company page
            # Adjust this URL pattern based on actual EdmundSEC structure
            search_url = f"{self.BASE_URL}/search"
            params = {'ticker': ticker}

            if company_name:
                params['company'] = company_name

            response = self.session.get(search_url, params=params, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Parse result listings
            # This is a template - adjust selectors based on actual EdmundSEC HTML
            documents = []

            # Look for document rows (adjust selector)
            doc_rows = soup.find_all(['tr', 'div'], class_=re.compile(r'document|filing|result', re.I))

            for row in doc_rows:
                doc = self._parse_document_row(row)
                if doc:
                    documents.append(doc)

            logger.info(f"Found {len(documents)} documents for {ticker}")
            return documents

        except requests.exceptions.RequestException as e:
            logger.error(f"Error listing transcripts: {e}")
            return []

    def _parse_document_row(self, row) -> Optional[dict]:
        """
        Parse a single document row from search results.
        Returns: dict with url, title, date, type or None if can't parse.
        """
        try:
            # Find link
            link = row.find('a', href=True)
            if not link:
                return None

            url = link.get('href')
            if not url.startswith('http'):
                url = urljoin(self.BASE_URL, url)

            title = link.get_text(strip=True)

            # Try to find date (adjust pattern based on actual HTML)
            date_text = None
            date_elem = row.find(['td', 'span', 'div'], class_=re.compile(r'date|filed', re.I))
            if date_elem:
                date_text = date_elem.get_text(strip=True)

            parsed_date = self._parse_date(date_text) if date_text else None

            # Determine document type
            doc_type = "unknown"
            if any(term in title.lower() for term in ['transcript', 'earnings call', 'conference call']):
                doc_type = "transcript"
            elif '8-k' in title.lower():
                doc_type = "8-k"

            return {
                'url': url,
                'title': title,
                'date': parsed_date,
                'type': doc_type,
            }

        except Exception as e:
            logger.warning(f"Error parsing document row: {e}")
            return None

    def _parse_date(self, date_text: str) -> Optional[date]:
        """Parse date string into date object."""
        if not date_text:
            return None

        # Try common date formats
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

    def find_candidate_docs_for_query(self, query: TranscriptQuery) -> list[dict]:
        """
        Filter documents to likely candidates for this query.
        """
        all_docs = self.list_transcripts(query.ticker, query.company_name)

        if not all_docs:
            return []

        candidates = []

        for doc in all_docs:
            score = self._score_doc_relevance(doc, query)
            if score > 0:
                doc['relevance_score'] = score
                candidates.append(doc)

        # Sort by relevance
        candidates.sort(key=lambda x: x['relevance_score'], reverse=True)

        logger.info(f"Filtered to {len(candidates)} candidate documents")
        return candidates[:10]  # Top 10

    def _score_doc_relevance(self, doc: dict, query: TranscriptQuery) -> float:
        """
        Score how relevant this document is to the query.
        Returns: relevance score (higher is better)
        """
        score = 0.0
        title_lower = doc['title'].lower()

        # Type match
        if doc['type'] == 'transcript':
            score += 5.0

        # Date proximity
        if query.event_date and doc['date']:
            diff_days = abs((doc['date'] - query.event_date).days)
            if diff_days == 0:
                score += 10.0
            elif diff_days <= 1:
                score += 8.0
            elif diff_days <= 3:
                score += 5.0
            elif diff_days <= 7:
                score += 2.0

        # Event hint match
        if query.event_hint:
            hint_words = set(query.event_hint.lower().split())
            title_words = set(title_lower.split())
            overlap = hint_words & title_words
            score += len(overlap) * 2.0

        # Event type match
        if query.event_type == "earnings":
            if any(term in title_lower for term in ['earnings', 'quarterly', 'q1', 'q2', 'q3', 'q4']):
                score += 3.0
        elif query.event_type == "conference":
            if 'conference' in title_lower:
                score += 3.0

        return score

    def download_and_parse_doc(self, doc_meta: dict) -> TranscriptCandidate:
        """
        Download and parse a document into a TranscriptCandidate.
        """
        if not self._logged_in:
            self.login()

        candidate = TranscriptCandidate(
            provider="EDMUNDSEC",
            source_url=doc_meta['url'],
            parsed_title=doc_meta['title'],
            parsed_date=doc_meta.get('date'),
        )

        try:
            logger.info(f"Downloading: {doc_meta['url']}")
            response = self.session.get(doc_meta['url'], timeout=30)
            response.raise_for_status()

            content_type = response.headers.get('Content-Type', '').lower()

            # Parse based on content type
            if 'pdf' in content_type:
                candidate.text = self._parse_pdf(response.content)
                candidate.raw_bytes = response.content
            else:
                # Assume HTML
                candidate.text = self._parse_html(response.text)

            # Try to extract metadata from content
            if candidate.text:
                self._extract_metadata(candidate)

            candidate.notes.append(f"Downloaded from EdmundSEC: {len(candidate.text or '')} chars")

        except Exception as e:
            logger.error(f"Error downloading/parsing document: {e}")
            candidate.notes.append(f"Error: {str(e)}")

        return candidate

    def _parse_pdf(self, pdf_bytes: bytes) -> str:
        """Extract text from PDF bytes."""
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
            logger.error("pdfplumber not installed - cannot parse PDF")
            return ""
        except Exception as e:
            logger.error(f"Error parsing PDF: {e}")
            return ""

    def _parse_html(self, html: str) -> str:
        """Extract text from HTML."""
        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Remove script and style elements
            for script in soup(['script', 'style', 'nav', 'footer', 'header']):
                script.decompose()

            # Try to find main content
            content = None
            for selector in [
                'article',
                ('div', {'class': re.compile(r'content|transcript|body', re.I)}),
                ('div', {'id': re.compile(r'content|transcript|body', re.I)}),
                'main',
            ]:
                if isinstance(selector, tuple):
                    content = soup.find(*selector)
                else:
                    content = soup.find(selector)
                if content:
                    break

            if not content:
                content = soup.body or soup

            # Extract text
            text = content.get_text(separator='\n', strip=True)

            # Clean up excessive whitespace
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            return '\n\n'.join(lines)

        except Exception as e:
            logger.error(f"Error parsing HTML: {e}")
            return ""

    def _extract_metadata(self, candidate: TranscriptCandidate) -> None:
        """Extract ticker/company/date from transcript text."""
        if not candidate.text:
            return

        # Look at first 500 characters
        header = candidate.text[:500]

        # Extract ticker (NYSE: TICKER) or (NASDAQ: TICKER)
        ticker_match = re.search(r'\((?:NYSE|NASDAQ|AMEX):\s*([A-Z]+)\)', header, re.I)
        if ticker_match:
            candidate.parsed_ticker = ticker_match.group(1).upper()

        # Extract company name (usually near the top)
        # Look for patterns like "Company Name, Inc." or "Company Name Corporation"
        company_match = re.search(r'^([A-Z][A-Za-z\s&,\.]+(?:Inc\.|Corp\.|Corporation|Company|Ltd\.))', header, re.M)
        if company_match:
            candidate.parsed_company_name = company_match.group(1).strip()

        # Extract date if present (various formats)
        date_patterns = [
            r'(\w+ \d{1,2},\s*\d{4})',  # November 12, 2025
            r'(\d{1,2}/\d{1,2}/\d{4})',  # 11/12/2025
        ]

        for pattern in date_patterns:
            date_match = re.search(pattern, header)
            if date_match:
                parsed = self._parse_date(date_match.group(1))
                if parsed:
                    candidate.parsed_date = parsed
                    break
