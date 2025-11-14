"""
Earnings Call Transcripts Collector
Supports multiple sources: Finnhub API, Fool.com scraping
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

        if progress_callback:
            progress_callback(f"Collecting earnings call transcripts for {self.config.ticker}...")

        # Try Finnhub API first if API key available
        if self.finnhub_key:
            if progress_callback:
                progress_callback("Trying Finnhub API...")
            finnhub_transcripts = self._collect_from_finnhub(progress_callback)
            transcripts.extend(finnhub_transcripts)
        else:
            if progress_callback:
                progress_callback("ℹ️ Finnhub API key not provided - skipping API source")

        # Try Fool.com scraping as fallback
        if len(transcripts) == 0:
            if progress_callback:
                progress_callback("Trying Fool.com scraping...")
            fool_transcripts = self._collect_from_fool(progress_callback)
            transcripts.extend(fool_transcripts)

        # Try Seeking Alpha as additional source
        if len(transcripts) < 5:  # If we don't have many, try another source
            if progress_callback:
                progress_callback("Trying Seeking Alpha...")
            sa_transcripts = self._collect_from_seeking_alpha(progress_callback)
            transcripts.extend(sa_transcripts)

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

    def _collect_from_finnhub(
        self,
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
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> List[Transcript]:
        """Collect from Motley Fool"""
        transcripts = []

        try:
            # Search for company transcripts on Fool
            search_url = f"https://www.fool.com/search/?q={self.config.ticker}+earnings+call+transcript"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

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
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> List[Transcript]:
        """Collect from Seeking Alpha"""
        transcripts = []

        try:
            # Note: Seeking Alpha often requires authentication for full transcripts
            # This is a basic implementation - may need enhancement
            search_url = f"https://seekingalpha.com/symbol/{self.config.ticker}/earnings/transcripts"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            response = requests.get(search_url, headers=headers, timeout=10)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Try to find transcript links (structure may vary)
                for link in soup.find_all('a', href=True)[:5]:
                    href = link.get('href', '')
                    if '/article/' in href and 'earnings' in href.lower():
                        if progress_callback:
                            progress_callback(f"⚠️ Seeking Alpha transcripts may require subscription")
                        break

        except Exception as e:
            logger.warning(f"Error accessing Seeking Alpha: {e}")

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
