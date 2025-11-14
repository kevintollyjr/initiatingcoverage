"""
Earnings Call Transcripts Collector
Supports multiple sources:
- API Ninjas (free for S&P 100 companies)
- Financial Modeling Prep API (free tier)
- Finnhub API (free tier)
- Fool.com scraping (fallback)
"""
from pathlib import Path
from typing import List, Optional, Callable
import logging
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import time
import re

from ..models import Transcript
from ..config import TickerConfig
from ..utils import ensure_dir, slugify_filename, save_text, save_json

logger = logging.getLogger(__name__)


class TranscriptsCollector:
    """Collect earnings call transcripts from multiple sources"""

    def __init__(self, ticker_config: TickerConfig, data_dir: Path):
        self.config = ticker_config
        self.data_dir = data_dir
        self.transcripts_dir = ensure_dir(data_dir / "ir" / "transcripts")

        # API keys
        self.api_ninjas_key = ticker_config.api_ninjas_key
        self.fmp_key = ticker_config.fmp_key
        self.finnhub_key = ticker_config.finnhub_key

    def collect(
        self,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> List[Transcript]:
        """
        Collect earnings call transcripts

        Args:
            progress_callback: Optional callback for progress updates

        Returns:
            List of Transcript objects
        """
        transcripts = []
        cutoff_date = datetime.now() - timedelta(days=365 * self.config.lookback_years)

        if progress_callback:
            progress_callback(f"Collecting earnings call transcripts for {self.config.ticker}...")
            progress_callback(f"Looking back {self.config.lookback_years} years (since {cutoff_date.strftime('%Y-%m-%d')})")

        # Try API Ninjas first (free for S&P 100 companies, covers 8,000+ companies on premium)
        if self.api_ninjas_key:
            if progress_callback:
                progress_callback("Trying API Ninjas (free for S&P 100)...")
            api_ninjas_transcripts = self._collect_from_api_ninjas(cutoff_date, progress_callback)
            transcripts.extend(api_ninjas_transcripts)

        # Try Financial Modeling Prep API if we don't have enough
        if len(transcripts) < 5 and self.fmp_key:
            if progress_callback:
                progress_callback("Trying Financial Modeling Prep API...")
            fmp_transcripts = self._collect_from_fmp(cutoff_date, progress_callback)
            transcripts.extend(fmp_transcripts)

        # Try Finnhub API if available and we don't have enough
        if len(transcripts) < 8 and self.finnhub_key:
            if progress_callback:
                progress_callback("Trying Finnhub API...")
            finnhub_transcripts = self._collect_from_finnhub(cutoff_date, progress_callback)
            transcripts.extend(finnhub_transcripts)

        # Try Fool.com scraping as last resort
        if len(transcripts) < 10:
            if progress_callback:
                progress_callback("Trying Fool.com...")
            fool_transcripts = self._collect_from_fool(cutoff_date, progress_callback)
            transcripts.extend(fool_transcripts)

        # Save transcripts index
        if transcripts:
            self._save_transcripts_index(transcripts)
            if progress_callback:
                progress_callback(f"✓ Collected {len(transcripts)} transcripts")
        else:
            if progress_callback:
                progress_callback("⚠️ No transcripts found. They may be behind paywalls or not publicly available.")
                progress_callback("💡 You can manually add transcripts to: " + str(self.transcripts_dir))

        return transcripts

    def _collect_from_api_ninjas(
        self,
        cutoff_date: datetime,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> List[Transcript]:
        """
        Collect from API Ninjas
        Free tier: S&P 100 companies only
        Premium: 8,000+ companies globally
        """
        transcripts = []

        try:
            url = "https://api.api-ninjas.com/v1/earningstranscript"
            headers = {'X-Api-Key': self.api_ninjas_key}
            params = {'ticker': self.config.ticker}

            if progress_callback:
                progress_callback(f"Requesting latest transcript for {self.config.ticker}...")

            response = requests.get(url, headers=headers, params=params, timeout=15)

            if response.status_code == 200:
                data = response.json()

                # API Ninjas returns latest transcript by default
                if data and isinstance(data, dict):
                    # Extract transcript information
                    transcript_text = data.get('transcript', '')
                    year = data.get('year')
                    quarter = data.get('quarter')

                    if transcript_text and year and quarter:
                        # Check if within timeframe
                        transcript_date = datetime(int(year), int(quarter) * 3, 1)
                        if transcript_date >= cutoff_date:
                            filename = f"{year}_Q{quarter}_{self.config.ticker}_earnings_call_apininjas.txt"
                            filepath = self.transcripts_dir / filename

                            # Format transcript
                            full_text = f"Source: API Ninjas\n"
                            full_text += f"Company: {self.config.ticker}\n"
                            full_text += f"Date: Q{quarter} {year}\n"
                            full_text += "=" * 80 + "\n\n"
                            full_text += transcript_text

                            save_text(full_text, filepath)

                            transcript = Transcript(
                                title=f"{self.config.ticker} Q{quarter} {year} Earnings Call",
                                fiscal_period=f"{year}Q{quarter}",
                                date=transcript_date,
                                source='api_ninjas',
                                url=f"https://api-ninjas.com/earningstranscript/{self.config.ticker}",
                                local_path=str(filepath),
                                has_text_extract=True
                            )
                            transcripts.append(transcript)

                            if progress_callback:
                                progress_callback(f"✓ Downloaded Q{quarter} {year} transcript from API Ninjas")
                        else:
                            if progress_callback:
                                progress_callback(f"⚠️ Latest transcript (Q{quarter} {year}) is outside lookback period")
                    else:
                        if progress_callback:
                            progress_callback(f"⚠️ Incomplete transcript data from API Ninjas")
                else:
                    if progress_callback:
                        progress_callback(f"⚠️ No transcript data returned from API Ninjas")

            elif response.status_code == 402:
                if progress_callback:
                    progress_callback(f"⚠️ HTTP 402 - {self.config.ticker} not in free S&P 100 tier (requires premium)")
            elif response.status_code == 404:
                if progress_callback:
                    progress_callback(f"⚠️ HTTP 404 - No transcripts found for {self.config.ticker}")
            else:
                if progress_callback:
                    progress_callback(f"⚠️ HTTP {response.status_code} - API Ninjas request failed")
                logger.warning(f"API Ninjas returned {response.status_code}: {response.text[:200]}")

        except Exception as e:
            logger.error(f"Error collecting from API Ninjas: {e}")
            if progress_callback:
                progress_callback(f"❌ Error with API Ninjas: {str(e)[:50]}")

        return transcripts

    def _collect_from_fmp(
        self,
        cutoff_date: datetime,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> List[Transcript]:
        """
        Collect from Financial Modeling Prep API
        Requires year and quarter parameters
        """
        transcripts = []

        try:
            # Calculate quarters to fetch based on lookback period
            current_year = datetime.now().year
            current_quarter = (datetime.now().month - 1) // 3 + 1
            start_year = cutoff_date.year

            if progress_callback:
                progress_callback(f"Fetching transcripts from {start_year} to {current_year}...")

            # Iterate through years and quarters
            for year in range(start_year, current_year + 1):
                for quarter in range(1, 5):
                    # Skip future quarters
                    if year == current_year and quarter > current_quarter:
                        continue

                    # Check if this quarter is within lookback period
                    quarter_date = datetime(year, quarter * 3, 1)
                    if quarter_date < cutoff_date:
                        continue

                    try:
                        url = f"https://financialmodelingprep.com/api/v3/earning_call_transcript/{self.config.ticker}"
                        params = {
                            'year': year,
                            'quarter': quarter,
                            'apikey': self.fmp_key
                        }

                        time.sleep(0.3)  # Rate limiting
                        response = requests.get(url, params=params, timeout=15)

                        if response.status_code == 200:
                            data = response.json()

                            # FMP returns list with single transcript or empty list
                            if data and isinstance(data, list) and len(data) > 0:
                                transcript_data = data[0]
                                transcript_text = transcript_data.get('content', '')

                                if transcript_text and len(transcript_text) > 500:
                                    filename = f"{year}_Q{quarter}_{self.config.ticker}_earnings_call_fmp.txt"
                                    filepath = self.transcripts_dir / filename

                                    # Format transcript
                                    full_text = f"Source: Financial Modeling Prep\n"
                                    full_text += f"Company: {self.config.ticker}\n"
                                    full_text += f"Date: Q{quarter} {year}\n"
                                    full_text += "=" * 80 + "\n\n"
                                    full_text += transcript_text

                                    save_text(full_text, filepath)

                                    transcript = Transcript(
                                        title=f"{self.config.ticker} Q{quarter} {year} Earnings Call",
                                        fiscal_period=f"{year}Q{quarter}",
                                        date=quarter_date,
                                        source='fmp',
                                        url=url,
                                        local_path=str(filepath),
                                        has_text_extract=True
                                    )
                                    transcripts.append(transcript)

                                    if progress_callback:
                                        progress_callback(f"✓ Downloaded Q{quarter} {year} transcript from FMP")

                    except Exception as e:
                        logger.warning(f"Error fetching FMP transcript for Q{quarter} {year}: {e}")
                        continue

            if progress_callback:
                if transcripts:
                    progress_callback(f"✓ Collected {len(transcripts)} transcripts from FMP")
                else:
                    progress_callback(f"⚠️ No transcripts found on FMP (may require paid plan or not available)")

        except Exception as e:
            logger.error(f"Error collecting from FMP: {e}")
            if progress_callback:
                progress_callback(f"❌ Error with FMP: {str(e)[:50]}")

        return transcripts

    def _collect_from_investing(
        self,
        cutoff_date: datetime,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> List[Transcript]:
        """Collect from Investing.com"""
        transcripts = []

        try:
            # Complete browser-like headers to avoid 403 errors
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Cache-Control': 'max-age=0'
            }

            # Try direct transcripts page for this ticker
            transcript_links = []

            # Approach 1: Main transcripts page - scan recent transcripts
            if progress_callback:
                progress_callback("Scanning Investing.com transcripts page...")

            main_url = "https://www.investing.com/news/transcripts"
            try:
                response = requests.get(main_url, headers=headers, timeout=15)
                if progress_callback:
                    progress_callback(f"HTTP {response.status_code} - Main transcripts page")
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')

                # Find all article links on the transcripts page
                for article in soup.find_all(['article', 'div'], class_=lambda x: x and ('article' in x.lower() or 'item' in x.lower())):
                    link = article.find('a', href=True)
                    if link:
                        href = link.get('href', '')
                        title = link.get_text(strip=True) or article.get_text(strip=True)[:200]

                        # Check if this transcript is for our ticker
                        if self.config.ticker.upper() in title.upper() or self.config.ticker.lower() in href.lower():
                            full_url = href if href.startswith('http') else f"https://www.investing.com{href}"

                            # Extract year from title
                            year_match = re.search(r'(\d{4})', title)
                            year = int(year_match.group(1)) if year_match else None

                            if year and datetime(year, 1, 1) >= cutoff_date:
                                transcript_links.append((full_url, title, year))
                                if progress_callback:
                                    progress_callback(f"Found: {title[:60]}...")
            except requests.exceptions.HTTPError as e:
                logger.warning(f"HTTP error scanning main transcripts page: {e}")
                if progress_callback:
                    progress_callback(f"⚠️ HTTP {e.response.status_code if hasattr(e, 'response') else '???'} error on main page, trying alternative methods...")
            except Exception as e:
                logger.warning(f"Error scanning main transcripts page: {e}")
                if progress_callback:
                    progress_callback(f"⚠️ Could not access main page ({str(e)[:50]}), trying alternative methods...")

            # Approach 2: Try searching for ticker + "earnings call transcript"
            if len(transcript_links) < 5:
                if progress_callback:
                    progress_callback("Searching for company-specific transcripts...")

                search_url = f"https://www.investing.com/search/?q={self.config.ticker}%20earnings%20call%20transcript"
                try:
                    time.sleep(2)
                    response = requests.get(search_url, headers=headers, timeout=15)
                    if progress_callback:
                        progress_callback(f"HTTP {response.status_code} - Search results")
                    response.raise_for_status()
                    soup = BeautifulSoup(response.text, 'html.parser')

                    # Look for links to transcript articles
                    for link in soup.find_all('a', href=True):
                        href = link.get('href', '')
                        text = link.get_text(strip=True)

                        if '/news/transcripts/' in href or 'earnings-call-transcript' in href.lower():
                            full_url = href if href.startswith('http') else f"https://www.investing.com{href}"

                            # Extract year
                            year_match = re.search(r'(\d{4})', text)
                            year = int(year_match.group(1)) if year_match else None

                            # Check if within timeframe
                            if year and datetime(year, 1, 1) >= cutoff_date:
                                if full_url not in [url for url, _, _ in transcript_links]:
                                    transcript_links.append((full_url, text, year))
                                    if progress_callback:
                                        progress_callback(f"Found: {text[:60]}...")
                except Exception as e:
                    logger.warning(f"Error searching: {e}")

            if not transcript_links and progress_callback:
                progress_callback(f"⚠️ No {self.config.ticker} transcripts found on Investing.com")
                return transcripts

            # Download transcripts
            if progress_callback:
                progress_callback(f"Found {len(transcript_links)} potential transcripts, downloading...")

            seen_urls = set()
            for i, (url, title, year) in enumerate(transcript_links[:15]):
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                try:
                    time.sleep(3)  # Polite scraping
                    if progress_callback:
                        progress_callback(f"Downloading transcript {i+1}/{min(len(transcript_links), 15)}...")

                    response = requests.get(url, headers=headers, timeout=15)
                    if progress_callback:
                        progress_callback(f"HTTP {response.status_code} - {url}")
                    response.raise_for_status()

                    soup = BeautifulSoup(response.text, 'html.parser')

                    # Try multiple selectors to find article content
                    article = None
                    selectors = [
                        ('article', {}),
                        ('div', {'class': 'WYSIWYG'}),
                        ('div', {'class': 'articlePage'}),
                        ('div', {'class': 'article'}),
                        ('div', {'id': 'article'}),
                        ('div', {'class': lambda x: x and 'content' in x.lower()}),
                    ]

                    for tag, attrs in selectors:
                        article = soup.find(tag, attrs)
                        if article:
                            break

                    if not article:
                        logger.warning(f"Could not find article content for {url}")
                        if progress_callback:
                            progress_callback(f"⚠️ Could not extract content from {title[:40]}...")
                        continue

                    # Extract text
                    text = article.get_text(separator='\n\n', strip=True)

                    if len(text) < 500:
                        logger.warning(f"Transcript too short ({len(text)} chars), skipping")
                        continue

                    # Extract quarter and year
                    quarter_match = re.search(r'Q([1-4])\s*(\d{4})', title + ' ' + text[:500])
                    if quarter_match:
                        quarter = int(quarter_match.group(1))
                        year = int(quarter_match.group(2))
                    else:
                        # Try other patterns
                        year_match = re.search(r'(\d{4})', title)
                        if year_match:
                            year = int(year_match.group(1))
                            # Guess quarter from month in URL or date
                            month_match = re.search(r'/(\d{2})/\d{2}/(\d{4})/', url)
                            if month_match:
                                month = int(month_match.group(1))
                                quarter = (month - 1) // 3 + 1
                            else:
                                quarter = ((i % 4) + 1)
                        else:
                            year = datetime.now().year
                            quarter = i + 1

                    # Check timeframe
                    transcript_date = datetime(year, (quarter * 3), 1)
                    if transcript_date < cutoff_date:
                        continue

                    filename = f"{year}_Q{quarter}_{self.config.ticker}_earnings_call_investing.txt"
                    filepath = self.transcripts_dir / filename

                    # Create formatted transcript
                    full_text = f"Source: Investing.com\n"
                    full_text += f"Title: {title}\n"
                    full_text += f"URL: {url}\n"
                    full_text += f"Date: Q{quarter} {year}\n"
                    full_text += "=" * 80 + "\n\n"
                    full_text += text

                    save_text(full_text, filepath)

                    transcript = Transcript(
                        title=title or f"{self.config.ticker} Q{quarter} {year} Earnings Call",
                        fiscal_period=f"{year}Q{quarter}",
                        date=transcript_date,
                        source='investing.com',
                        url=url,
                        local_path=str(filepath),
                        has_text_extract=True
                    )
                    transcripts.append(transcript)

                    if progress_callback:
                        progress_callback(f"✓ Downloaded Q{quarter} {year} transcript ({len(text)} chars)")

                except Exception as e:
                    logger.warning(f"Error downloading {url}: {e}")
                    if progress_callback:
                        progress_callback(f"⚠️ Error downloading transcript: {str(e)}")
                    continue

        except Exception as e:
            logger.error(f"Error collecting from Investing.com: {e}")
            if progress_callback:
                progress_callback(f"❌ Error with Investing.com: {str(e)}")

        return transcripts

    def _collect_from_finnhub(
        self,
        cutoff_date: datetime,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> List[Transcript]:
        """Collect from Finnhub API"""
        transcripts = []

        try:
            # Get transcript list
            url = f"https://finnhub.io/api/v1/stock/earnings-transcript/list"
            params = {
                'symbol': self.config.ticker,
                'token': self.finnhub_key
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if 'transcripts' in data:
                for item in data['transcripts'][:20]:  # Limit to 20 most recent
                    transcript_id = item.get('id')
                    quarter = item.get('quarter')
                    year = item.get('year')

                    # Check if within timeframe
                    transcript_date = datetime(year, (quarter * 3), 1)
                    if transcript_date < cutoff_date:
                        continue

                    # Get full transcript
                    time.sleep(0.5)  # Rate limiting
                    transcript_url = f"https://finnhub.io/api/v1/stock/earnings-transcript"
                    params = {
                        'id': transcript_id,
                        'token': self.finnhub_key
                    }

                    response = requests.get(transcript_url, params=params, timeout=10)
                    response.raise_for_status()
                    transcript_data = response.json()

                    # Save transcript
                    filename = f"{year}_Q{quarter}_{self.config.ticker}_earnings_call.txt"
                    filepath = self.transcripts_dir / filename

                    # Format transcript text
                    text = self._format_finnhub_transcript(transcript_data)
                    save_text(text, filepath)

                    transcript = Transcript(
                        title=f"{self.config.ticker} Q{quarter} {year} Earnings Call",
                        fiscal_period=f"{year}Q{quarter}",
                        date=datetime(year, (quarter * 3), 1),
                        source='finnhub',
                        url=f"https://finnhub.io/api/v1/stock/earnings-transcript?id={transcript_id}",
                        local_path=str(filepath),
                        has_text_extract=True
                    )
                    transcripts.append(transcript)

                    if progress_callback:
                        progress_callback(f"Downloaded {year} Q{quarter} transcript")

        except Exception as e:
            logger.error(f"Error collecting from Finnhub: {e}")
            if progress_callback:
                progress_callback(f"Error with Finnhub API: {str(e)}")

        return transcripts

    def _collect_from_fool(
        self,
        cutoff_date: datetime,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> List[Transcript]:
        """Collect from Motley Fool"""
        transcripts = []

        try:
            # Complete browser-like headers to avoid 403 errors
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }

            # Search for company transcripts on Fool
            search_url = f"https://www.fool.com/search/?q={self.config.ticker}+earnings+call+transcript"

            response = requests.get(search_url, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Find transcript links
            transcript_links = []
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                if 'earnings-call-transcript' in href or 'earnings/call-transcripts' in href:
                    if self.config.ticker.lower() in href.lower():
                        full_url = href if href.startswith('http') else f"https://www.fool.com{href}"
                        transcript_links.append(full_url)

            # Download transcripts
            for i, url in enumerate(transcript_links[:10]):  # Limit to 10
                try:
                    time.sleep(2)  # Polite scraping
                    response = requests.get(url, headers=headers, timeout=10)
                    response.raise_for_status()

                    soup = BeautifulSoup(response.text, 'html.parser')

                    # Extract transcript content
                    content = soup.find('article') or soup.find('div', class_='article-body')
                    if content:
                        text = content.get_text(strip=True, separator='\n\n')

                        # Extract date and quarter from URL or content
                        date_match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', url)
                        quarter_match = re.search(r'Q(\d)\s*(\d{4})', text[:500])

                        if quarter_match:
                            quarter = int(quarter_match.group(1))
                            year = int(quarter_match.group(2))
                        elif date_match:
                            year = int(date_match.group(1))
                            month = int(date_match.group(2))
                            quarter = (month - 1) // 3 + 1
                        else:
                            year = datetime.now().year
                            quarter = i + 1

                        # Check if within timeframe
                        transcript_date = datetime(year, (quarter * 3), 1)
                        if transcript_date < cutoff_date:
                            continue

                        filename = f"{year}_Q{quarter}_{self.config.ticker}_earnings_call_fool.txt"
                        filepath = self.transcripts_dir / filename
                        save_text(text, filepath)

                        transcript = Transcript(
                            title=f"{self.config.ticker} Q{quarter} {year} Earnings Call",
                            fiscal_period=f"{year}Q{quarter}",
                            date=datetime(year, (quarter * 3), 1),
                            source='fool.com',
                            url=url,
                            local_path=str(filepath),
                            has_text_extract=True
                        )
                        transcripts.append(transcript)

                        if progress_callback:
                            progress_callback(f"Downloaded {year} Q{quarter} transcript from Fool")

                except Exception as e:
                    logger.warning(f"Error downloading transcript from {url}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error collecting from Fool.com: {e}")
            if progress_callback:
                progress_callback(f"Error scraping Fool.com: {str(e)}")

        return transcripts

    def _collect_from_seeking_alpha(
        self,
        cutoff_date: datetime,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> List[Transcript]:
        """Collect from Seeking Alpha"""
        transcripts = []

        try:
            # Complete browser-like headers to avoid 403 errors
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }

            # Try earnings transcripts page for this ticker
            transcripts_url = f"https://seekingalpha.com/symbol/{self.config.ticker}/earnings/transcripts"

            try:
                response = requests.get(transcripts_url, headers=headers, timeout=15)
                if progress_callback:
                    progress_callback(f"HTTP {response.status_code} - Seeking Alpha transcripts page")
                response.raise_for_status()

                soup = BeautifulSoup(response.text, 'html.parser')

                # Find transcript article links
                transcript_links = []
                for link in soup.find_all('a', href=True):
                    href = link.get('href', '')
                    text = link.get_text(strip=True)

                    # Look for article links with earnings keywords
                    if '/article/' in href and ('earnings' in text.lower() or 'transcript' in text.lower()):
                        full_url = href if href.startswith('http') else f"https://seekingalpha.com{href}"

                        # Extract year from link text or URL
                        year_match = re.search(r'(\d{4})', text + href)
                        if year_match:
                            year = int(year_match.group(1))
                            if datetime(year, 1, 1) >= cutoff_date:
                                transcript_links.append((full_url, text))
                                if progress_callback:
                                    progress_callback(f"Found: {text[:60]}...")

                if not transcript_links and progress_callback:
                    progress_callback(f"⚠️ No {self.config.ticker} transcripts found on Seeking Alpha")
                    progress_callback("💡 Note: Seeking Alpha often requires subscription for full transcripts")
                    return transcripts

                # Download transcripts (limit to 10)
                for i, (url, title) in enumerate(transcript_links[:10]):
                    try:
                        time.sleep(3)  # Polite scraping
                        if progress_callback:
                            progress_callback(f"Downloading transcript {i+1}/{min(len(transcript_links), 10)}...")

                        response = requests.get(url, headers=headers, timeout=15)
                        if progress_callback:
                            progress_callback(f"HTTP {response.status_code} - {url}")
                        response.raise_for_status()

                        soup = BeautifulSoup(response.text, 'html.parser')

                        # Try multiple selectors for article content
                        article = None
                        selectors = [
                            ('article', {}),
                            ('div', {'class': 'article-content'}),
                            ('div', {'data-test-id': 'content-container'}),
                            ('div', {'id': 'a-body'}),
                            ('section', {'data-test-id': 'article-content'})
                        ]

                        for tag, attrs in selectors:
                            article = soup.find(tag, attrs)
                            if article:
                                break

                        if not article:
                            if progress_callback:
                                progress_callback(f"⚠️ Could not extract content (may require login)")
                            continue

                        # Extract text
                        text = article.get_text(separator='\n\n', strip=True)

                        if len(text) < 500:
                            if progress_callback:
                                progress_callback(f"⚠️ Content too short (may be paywalled)")
                            continue

                        # Extract quarter and year
                        quarter_match = re.search(r'Q([1-4])\s*(\d{4})', title + ' ' + text[:500])
                        if quarter_match:
                            quarter = int(quarter_match.group(1))
                            year = int(quarter_match.group(2))
                        else:
                            year_match = re.search(r'(\d{4})', title)
                            year = int(year_match.group(1)) if year_match else datetime.now().year
                            quarter = ((i % 4) + 1)

                        # Check timeframe
                        transcript_date = datetime(year, (quarter * 3), 1)
                        if transcript_date < cutoff_date:
                            continue

                        filename = f"{year}_Q{quarter}_{self.config.ticker}_earnings_call_seekingalpha.txt"
                        filepath = self.transcripts_dir / filename

                        # Create formatted transcript
                        full_text = f"Source: Seeking Alpha\n"
                        full_text += f"Title: {title}\n"
                        full_text += f"URL: {url}\n"
                        full_text += f"Date: Q{quarter} {year}\n"
                        full_text += "=" * 80 + "\n\n"
                        full_text += text

                        save_text(full_text, filepath)

                        transcript = Transcript(
                            title=title or f"{self.config.ticker} Q{quarter} {year} Earnings Call",
                            fiscal_period=f"{year}Q{quarter}",
                            date=transcript_date,
                            source='seekingalpha.com',
                            url=url,
                            local_path=str(filepath),
                            has_text_extract=True
                        )
                        transcripts.append(transcript)

                        if progress_callback:
                            progress_callback(f"✓ Downloaded Q{quarter} {year} transcript ({len(text)} chars)")

                    except Exception as e:
                        logger.warning(f"Error downloading {url}: {e}")
                        if progress_callback:
                            progress_callback(f"⚠️ Error downloading transcript: {str(e)}")
                        continue

            except requests.exceptions.HTTPError as e:
                if progress_callback:
                    progress_callback(f"⚠️ HTTP {e.response.status_code if hasattr(e, 'response') else '???'} error accessing Seeking Alpha")
            except Exception as e:
                logger.warning(f"Error accessing Seeking Alpha: {e}")
                if progress_callback:
                    progress_callback(f"⚠️ Could not access Seeking Alpha ({str(e)[:50]})")

        except Exception as e:
            logger.error(f"Error collecting from Seeking Alpha: {e}")
            if progress_callback:
                progress_callback(f"❌ Error with Seeking Alpha: {str(e)}")

        return transcripts

    def _format_finnhub_transcript(self, data: dict) -> str:
        """Format Finnhub transcript data into readable text"""
        text = ""

        # Add header
        if 'quarter' in data and 'year' in data:
            text += f"Earnings Call Transcript - Q{data['quarter']} {data['year']}\n"
            text += "=" * 60 + "\n\n"

        # Add participants
        if 'participant' in data:
            text += "PARTICIPANTS\n"
            text += "-" * 60 + "\n"
            for p in data['participant']:
                name = p.get('name', 'Unknown')
                title = p.get('title', '')
                text += f"{name} - {title}\n"
            text += "\n"

        # Add transcript content
        if 'transcript' in data:
            for section in data['transcript']:
                speaker = section.get('speaker', 'Unknown')
                content = section.get('speech', '')
                text += f"\n{speaker}:\n"
                text += content + "\n"

        return text

    def _save_transcripts_index(self, transcripts: List[Transcript]):
        """Save transcripts index to JSON"""
        index_path = self.transcripts_dir / "transcripts_index.json"
        index_data = [t.to_dict() for t in transcripts]
        save_json(index_data, index_path)
